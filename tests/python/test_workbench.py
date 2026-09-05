import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from esports_data.workbench import Workbench
from esports_data.recheck import run_checks

ROOT=Path(__file__).resolve().parents[2]

class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.b=Workbench(ROOT,Path(self.tmp.name)/'review.db','test-reviewer')
        self.entry=self.b.state()['entries'][0]
    def tearDown(self):self.b.db.close();self.tmp.cleanup()
    def draft(self):
        return {'entry_id':self.entry['id'],'prior_sha256':self.b.project()['hashes'][self.entry['id']],'changes':{'operational_status':'needs_review'},'reason':'공식 운영 근거 추가 확인 필요','checked_at':'2026-09-05','next_review_at':'2026-12-04','status_supported':False,'evidence':[]}
    def save(self,draft=None):
        request={'action':'save','command_id':'save-command-001','draft_id':'review-test-00000001','version':0,'draft':draft or self.draft()}
        return request,self.b.command(request)
    def test_import_preserves_all_decisions_and_is_idempotent(self):
        before=self.b.state()['candidates'];self.b.import_ledgers();self.assertEqual(before,self.b.state()['candidates'])
        expected=json.loads((ROOT/'data/discovery/candidates.v1.json').read_text())['candidates']
        self.assertEqual({c['id']:c['status'] for c in before},{c['id']:c['status'] for c in expected})
    def test_approval_requires_human_and_replay_is_exact(self):
        request,result=self.save();self.assertEqual(result,self.b.command(request))
        approve={'action':'approve','command_id':'approve-command-001','draft_id':result['id'],'version':0}
        with self.assertRaises(ValueError):self.b.command(approve)
        approve['human_confirmed']=True
        result=self.b.command(approve);self.assertEqual(result,self.b.command(approve))
        entry=next(e for e in self.b.project()['site']['entries'] if e['id']==self.entry['id'])
        self.assertEqual(entry['operational_review']['checked_at'],'2026-09-05')
        self.assertIsNone(entry['status_checked_at'])
        self.assertEqual(len(self.b.ledger()['reviews']),1)
    def test_stale_draft_and_changed_replay_rejected(self):
        request,_=self.save();request['draft']['reason']='다른 이유'
        with self.assertRaises(ValueError):self.b.command(request)
        request['command_id']='save-command-002';request['version']=8
        with self.assertRaises(ValueError):self.b.command(request)
    def test_status_without_evidence_rejected(self):
        d=self.draft();d['changes']['operational_status']='current';_,r=self.save(d)
        with self.assertRaises(ValueError):self.b.command({'action':'approve','command_id':'approve-command-001','draft_id':r['id'],'version':0,'human_confirmed':True})
        self.assertEqual(self.b.ledger()['reviews'],[])
    def test_pii_draft_rejected(self):
        d=self.draft();d['reason']='contact person@example.com'
        with self.assertRaises(ValueError):self.save(d)
    def test_restart_preserves_approved_history(self):
        _,r=self.save();self.b.command({'action':'approve','command_id':'approve-command-001','draft_id':r['id'],'version':0,'human_confirmed':True})
        other=Workbench(ROOT,Path(self.tmp.name)/'review.db','test-reviewer')
        self.assertEqual(self.b.ledger(),other.ledger());other.db.close()
    def test_source_failure_never_changes_public_status(self):
        before=self.b.project()['site']
        with patch('esports_data.recheck.inspect_url',return_value={'url':None,'result':'FETCH_FAILED','sha256':None}),patch('esports_data.recheck._atomic_json'):
            report=run_checks(self.b)
        self.assertEqual(report['attempted_entries'],30)
        self.assertEqual(report['fact_reviews_completed'],0)
        self.assertEqual(self.b.project()['site'],before)

    def test_candidate_decision_updates_both_ledgers_atomically(self):
        from esports_data.workbench import encoded
        candidate={'id':'candidate-test','canonical_url':'https://www.moe.go.kr/test','url_sha256':'c'*64,'status':'needs_review'}
        with self.b.db:
            self.b.db.execute('INSERT INTO wb_candidates(id,payload,status) VALUES (?,?,?)',(candidate['id'],encoded(candidate),'needs_review'))
            self.b.db.execute('INSERT INTO wb_seen VALUES (?,?)',('c'*64,encoded({'entry_ids':[],'decision':'needs_review'})))
        command={'action':'candidate','command_id':'candidate-command-001','candidate_id':candidate['id'],'version':0,'decision':'accepted','entry_id':'unknown','reason_code':'OFFICIAL_EVIDENCE'}
        with self.assertRaises(ValueError):self.b.command(command)
        self.assertEqual(self.b.db.execute('SELECT status FROM wb_candidates WHERE id=?',(candidate['id'],)).fetchone()[0],'needs_review')
        command['entry_id']=self.entry['id'];self.b.command(command)
        self.assertEqual(json.loads(self.b.db.execute('SELECT payload FROM wb_seen WHERE id=?',('c'*64,)).fetchone()[0])['entry_ids'],[self.entry['id']])

    def test_event_suggestions_keep_years_separate(self):
        from esports_data.weekly_discovery import event_digest
        self.assertIsNone(event_digest('학교 e스포츠 대회'))
        a=event_digest('2025 부산교육청 학교 e스포츠 대회')
        b=event_digest('2026 부산교육청 학교 e스포츠 대회')
        self.assertIsNotNone(a);self.assertNotEqual(a,b)

    def test_unregistered_evidence_cannot_be_approved(self):
        d=self.draft();d['changes']['operational_status']='current';d['status_supported']=True
        d['evidence']=[{'url':'https://example.org/article','sha256':'a'*64,'summary':'공식 근거 주장','publisher_id':'moe','official':True}]
        _,r=self.save(d)
        with self.assertRaises(ValueError):self.b.command({'action':'approve','command_id':'approve-command-001','draft_id':r['id'],'version':0,'human_confirmed':True})
