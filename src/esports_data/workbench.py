"""Private, transactional review workbench; exports are proposals for Git review.

No HTTP response bodies or article titles are persisted by collection. Approval
is an explicit operator command, never a consequence of a successful fetch.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
import subprocess
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .review_safety import require_safe
from .weekly_discovery import canonicalize_url, title_digest, _atomic_json


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def today():
    return datetime.now(timezone.utc).date().isoformat()


class Workbench:
    def __init__(self, root: Path, database: Path, reviewer: str):
        import re
        if not re.fullmatch(r'[a-z][a-z0-9_-]{2,63}', reviewer):
            raise ValueError('Opaque reviewer ID required')
        self.root, self.reviewer = root.resolve(), reviewer
        database.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(database)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS wb_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS wb_candidates (id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS wb_seen (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS wb_drafts (id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft', version INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS wb_approvals (sequence INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS wb_commands (id TEXT PRIMARY KEY, digest TEXT NOT NULL, result TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS wb_attempts (entry_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        ''')
        self.refresh_base()
        self.import_ledgers()
        if not self.db.execute("SELECT 1 FROM wb_meta WHERE key='pilot_ids'").fetchone():
            entries=self.project()['site']['entries']
            entries.sort(key=lambda e:(not (e['resource_type']=='school' or e['category']=='교육청대회·사업'),e.get('operational_review',{}).get('checked_at',''),str(e.get('year') or ''),e['id']))
            with self.db:self.db.execute("INSERT INTO wb_meta VALUES ('pilot_ids',?)",(encoded([e['id'] for e in entries[:30]]),))

    def refresh_base(self):
        with tempfile.TemporaryDirectory(prefix='esports-workbench-') as directory:
            subprocess.run(['node', 'scripts/extract-data.mjs', '--base-only', '--output', directory], cwd=self.root, check=True, capture_output=True)
            self.base = json.loads((Path(directory) / 'data/site.v3.json').read_text())
        ledger = json.loads((self.root / 'data/approved-reviews.v1.json').read_text())
        with self.db:
            existing = [json.loads(row[0]) for row in self.db.execute('SELECT payload FROM wb_approvals ORDER BY sequence')]
            common = min(len(existing),len(ledger['reviews']))
            if existing[:common] != ledger['reviews'][:common]:
                raise ValueError('Approved history diverged; reconcile before review')
            for review in ledger['reviews'][len(existing):]:
                self.db.execute('INSERT INTO wb_approvals(id,payload) VALUES (?,?)',(review['id'],encoded(review)))
        self.project()  # Reject changed baseline or stale imported receipts.

    def ledger(self):
        return {'schema_version':1,'reviews':[json.loads(row[0]) for row in self.db.execute('SELECT payload FROM wb_approvals ORDER BY sequence')]}

    def project(self, ledger=None):
        process = subprocess.run(['node','scripts/review-project.mjs'], cwd=self.root, input=encoded({'base':self.base,'ledger':ledger or self.ledger()}),text=True,capture_output=True)
        if process.returncode:
            raise ValueError('Review projection conflict or invalid evidence')
        return json.loads(process.stdout)

    def import_ledgers(self):
        candidates = json.loads((self.root/'data/discovery/candidates.v1.json').read_text())['candidates']
        seen = json.loads((self.root/'data/discovery/seen.v1.json').read_text())['items']
        with self.db:
            for row in candidates:
                old=self.db.execute('SELECT payload,status,version FROM wb_candidates WHERE id=?',(row['id'],)).fetchone()
                if old is None:
                    self.db.execute('INSERT INTO wb_candidates(id,payload,status) VALUES (?,?,?)',(row['id'],encoded(row),row['status']))
                elif old['version']==0:
                    self.db.execute('UPDATE wb_candidates SET payload=?,status=? WHERE id=?',(encoded(row),row['status'],row['id']))
                elif row['status'] != 'needs_review' and row['status'] != old['status']:
                    raise ValueError('Candidate review conflict')
            for row in seen:
                self.db.execute('INSERT OR IGNORE INTO wb_seen VALUES (?,?)',(row['url_sha256'],encoded(row)))

    def state(self):
        projection = self.project()
        attempts={r['entry_id']:json.loads(r['payload']) for r in self.db.execute('SELECT * FROM wb_attempts')}
        entries=projection['site']['entries']
        entries.sort(key=lambda e:(not (e['resource_type']=='school' or e['category']=='교육청대회·사업'),e.get('operational_review',{}).get('checked_at',''),str(e.get('year') or ''),e['id']))
        candidates=[{**json.loads(r['payload']),'status':r['status'],'version':r['version']} for r in self.db.execute('SELECT * FROM wb_candidates ORDER BY id')]
        drafts=[{**json.loads(r['payload']),'status':r['status'],'version':r['version']} for r in self.db.execute('SELECT * FROM wb_drafts ORDER BY id')]
        pending=[c for c in candidates if c['status']=='needs_review']
        waits=[]
        for c in pending:
            try: waits.append((date.fromisoformat(today())-date.fromisoformat(c['discovered_at'][:10])).days)
            except (KeyError,ValueError): pass
        return {'entries':entries,'hashes':projection['hashes'],'candidates':candidates,'drafts':drafts,'attempts':attempts,'pilot_ids':json.loads(self.db.execute("SELECT value FROM wb_meta WHERE key='pilot_ids'").fetchone()[0]),'metrics':{'entries':len(entries),'attempted':len(attempts),'approved_reviews':len(self.ledger()['reviews']),'pending_candidates':len(pending),'oldest_wait_days':max(waits,default=0),'duplicate_candidates':sum(c['status']=='duplicate' for c in candidates),'candidates':len(candidates),'official_evidence_reviews':sum(bool(r['evidence']) for r in self.ledger()['reviews']),'official_evidence_rate':sum(bool(r['evidence']) for r in self.ledger()['reviews'])/len(self.ledger()['reviews']) if self.ledger()['reviews'] else None,'duplicate_url_rate':sum(c['status']=='duplicate' for c in candidates)/len(candidates) if candidates else None,'event_groups':len({c['event_sha256'] for c in candidates if c.get('event_sha256')})}}

    def command(self, request):
        import re
        command_id=request.get('command_id','')
        if not re.fullmatch(r'[a-zA-Z0-9-]{8,100}', command_id): raise ValueError('Command ID required')
        fingerprint=digest(request)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            old=self.db.execute('SELECT * FROM wb_commands WHERE id=?',(command_id,)).fetchone()
            if old:
                if old['digest']!=fingerprint: raise ValueError('Command replay mismatch')
                return json.loads(old['result'])
            action=request.get('action')
            if action=='save': result=self.save(request)
            elif action=='approve': result=self.approve(request)
            elif action=='candidate': result=self.decide_candidate(request)
            else: raise ValueError('Unsupported command')
            self.db.execute('INSERT INTO wb_commands VALUES (?,?,?)',(command_id,fingerprint,encoded(result)))
            return result

    def save(self, request):
        draft=request['draft']
        projection=self.project()
        if (not draft.get('new_entry') and draft.get('entry_id') not in projection['hashes']) or projection['hashes'].get(draft.get('entry_id'))!=draft.get('prior_sha256'): raise ValueError('Entry changed; reload')
        # Keep drafts PII-free too: no raw documents or reviewer personal names.
        require_safe(draft)
        draft_id=request['draft_id']
        if not isinstance(draft_id,str) or not draft_id.startswith('review-'): raise ValueError('Invalid draft ID')
        old=self.db.execute('SELECT * FROM wb_drafts WHERE id=?',(draft_id,)).fetchone()
        if old and (old['version']!=request['version'] or old['status']!='draft'): raise ValueError('Draft conflict')
        payload={**draft,'id':draft_id}
        if old:
            self.db.execute('UPDATE wb_drafts SET payload=?,version=version+1 WHERE id=?',(encoded(payload),draft_id))
        else:
            if request.get('version')!=0: raise ValueError('Draft version conflict')
            self.db.execute('INSERT INTO wb_drafts(id,payload) VALUES (?,?)',(draft_id,encoded(payload)))
        return {'id':draft_id,'version':(old['version']+1 if old else 0)}

    def approve(self, request):
        if request.get('human_confirmed') is not True: raise ValueError('Explicit human confirmation required')
        row=self.db.execute('SELECT * FROM wb_drafts WHERE id=?',(request['draft_id'],)).fetchone()
        if not row or row['status']!='draft' or row['version']!=request['version']: raise ValueError('Draft conflict')
        draft=json.loads(row['payload'])
        review={**draft,'approved_by':self.reviewer,'approved_at':today()}
        for evidence in review['evidence']:
            if canonicalize_url(evidence['url'])!=evidence['url']: raise ValueError('Canonical public HTTPS evidence required')
        require_safe(review)
        if review['checked_at']>today(): raise ValueError('Future observation')
        ledger=self.ledger(); ledger['reviews'].append(review)
        self.project(ledger)
        self.db.execute('INSERT INTO wb_approvals(id,payload) VALUES (?,?)',(review['id'],encoded(review)))
        self.db.execute("UPDATE wb_drafts SET status='approved',version=version+1 WHERE id=?",(review['id'],))
        return {'id':review['id'],'status':'approved'}

    def decide_candidate(self, request):
        row=self.db.execute('SELECT * FROM wb_candidates WHERE id=?',(request['candidate_id'],)).fetchone()
        if not row or row['version']!=request['version'] or row['status']!='needs_review': raise ValueError('Candidate conflict')
        decision=request['decision']; entry_id=request.get('entry_id')
        if decision not in {'accepted','duplicate','rejected','needs_review'}: raise ValueError('Invalid decision')
        if entry_id and entry_id not in self.project()['hashes']: raise ValueError('Unknown entry')
        if decision=='accepted' and not entry_id: raise ValueError('Accepted requires public entry')
        reason=request.get('reason_code')
        if reason not in {'OFFICIAL_EVIDENCE','SAME_EVENT','OUT_OF_SCOPE','NO_OFFICIAL_EVIDENCE','MANUAL_REVIEW'}: raise ValueError('Reason code required')
        item=json.loads(row['payload']); item.update(status=decision,reason_code=reason,reviewed_at=today())
        if entry_id: item['entry_id']=entry_id
        seen=self.db.execute('SELECT payload FROM wb_seen WHERE id=?',(item['url_sha256'],)).fetchone()
        if not seen: raise ValueError('Seen ledger missing')
        seen=json.loads(seen[0]);seen.update(decision=decision,reviewed_at=today())
        if entry_id: seen['entry_ids']=sorted(set(seen.get('entry_ids',[])+[entry_id]))
        self.db.execute('UPDATE wb_seen SET payload=? WHERE id=?',(encoded(seen),item['url_sha256']))
        self.db.execute('UPDATE wb_candidates SET status=?,payload=?,version=version+1 WHERE id=?',(decision,encoded(item),item['id']))
        return {'id':item['id'],'status':decision}

    def export(self):
        # Fixed ignored directory: HTTP callers cannot choose filesystem paths.
        self.refresh_base()
        projection=self.project()
        target=self.root/'artifacts/workbench/export'
        _atomic_json(target/'approved-reviews.v1.json',self.ledger())
        _atomic_json(target/'site.v3.json',projection['site'])
        _atomic_json(target/'candidates.v1.json',{'schema_version':1,'candidates':[json.loads(r[0]) for r in self.db.execute('SELECT payload FROM wb_candidates ORDER BY id')]})
        _atomic_json(target/'seen.v1.json',{'schema_version':1,'canonicalization_version':1,'items':[json.loads(r[0]) for r in self.db.execute('SELECT payload FROM wb_seen ORDER BY id')]})
        manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in target.glob('*.json') if p.name!='manifest.json'}
        _atomic_json(target/'manifest.json',{'schema_version':1,'sha256':manifest,'publication':'proposal_only'})
        return {'path':'artifacts/workbench/export','status':'proposal_only','manifest':manifest}
