"""Bounded source reachability attempts, never automatic fact verification."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date,timedelta
from hashlib import sha256
from urllib.parse import urlsplit
import json
import re
from .weekly_discovery import _fetch_document, canonicalize_url, DiscoveryError, _atomic_json
from .workbench import encoded, today, digest


def inspect_url(raw):
    url=canonicalize_url(raw)
    if not url:return {'url':None,'result':'UNSUPPORTED_URL','sha256':None}
    try:
        body=_fetch_document(url)
        return {'url':url,'result':'FETCHED_UNVERIFIED','sha256':sha256(body).hexdigest()}
    except (DiscoveryError,OSError):
        return {'url':url,'result':'FETCH_FAILED','sha256':None}


def run_checks(workbench, batch='pilot'):
    state=workbench.state()
    entries=[e for e in state['entries'] if batch=='all' or e['id'] in state['pilot_ids']]
    urls={e['id']:[u for u in re.findall(r'https?://[^\s;,)\]]+',e['source'])][:3] for e in entries}
    unique=sorted({url for row in urls.values() for url in row})
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=dict(zip(unique,pool.map(inspect_url,unique)))
    day=today(); next_day=(date.fromisoformat(day)+timedelta(days=90)).isoformat()
    with workbench.db:
        for entry in entries:
            evidence=[results[url] for url in urls[entry['id']]]
            result='MANUAL_FACT_REVIEW_REQUIRED' if any(e['result']=='FETCHED_UNVERIFIED' for e in evidence) else 'SOURCE_UNAVAILABLE' if evidence else 'NO_WEB_SOURCE'
            attempt={'entry_id':entry['id'],'checked_at':day,'next_review_at':next_day,'reason_code':result,'checks':evidence,'fact_review':'pending','batch':'pilot' if entry['id'] in state['pilot_ids'] else 'remaining'}
            draft_id='review-auto-'+digest({'entry_id':entry['id'],'day':day,'prior':state['hashes'][entry['id']]})[:24]
            reason={'MANUAL_FACT_REVIEW_REQUIRED':'등록 원문에 접근했으나 운영 여부의 사실 검토가 필요합니다.','SOURCE_UNAVAILABLE':'등록 원문에 접근하지 못해 대체 공식 근거 확인이 필요합니다.','NO_WEB_SOURCE':'검토 가능한 웹 근거를 추가로 확인해야 합니다.'}[result]
            draft={'id':draft_id,'entry_id':entry['id'],'prior_sha256':state['hashes'][entry['id']],'changes':{'operational_status':'needs_review'},'reason':reason,'checked_at':day,'next_review_at':next_day,'status_supported':False,'evidence':[]}
            workbench.db.execute('INSERT OR IGNORE INTO wb_drafts(id,payload) VALUES (?,?)',(draft_id,encoded(draft)))
            workbench.db.execute('INSERT INTO wb_attempts VALUES (?,?) ON CONFLICT(entry_id) DO UPDATE SET payload=excluded.payload',(entry['id'],encoded(attempt)))
    aggregate={'schema_version':1,'checked_at':day,'batch':batch,'attempted_entries':len(entries),'pilot_entries':sum(e['id'] in state['pilot_ids'] for e in entries),'urls_attempted':len(unique),'urls_fetched':sum(v['result']=='FETCHED_UNVERIFIED' for v in results.values()),'fact_reviews_completed':0,'public_changes':0,'next_review_at':next_day,'reason_counts':{reason:sum(json.loads(r[0])['reason_code']==reason for r in workbench.db.execute('SELECT payload FROM wb_attempts')) for reason in ['MANUAL_FACT_REVIEW_REQUIRED','SOURCE_UNAVAILABLE','NO_WEB_SOURCE']}}
    _atomic_json(workbench.root/f'artifacts/workbench/recheck-{batch}.json',aggregate)
    return aggregate


def main():
    import argparse
    from pathlib import Path
    from .workbench import Workbench
    parser=argparse.ArgumentParser();parser.add_argument('--batch',choices=['pilot','all'],default='pilot');parser.add_argument('--root',default='.')
    args=parser.parse_args();root=Path(args.root).resolve()
    bench=Workbench(root,root/'artifacts/workbench/reviews.sqlite3','source-checker')
    print(encoded(run_checks(bench,args.batch)))

if __name__=='__main__':main()
