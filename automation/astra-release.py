#!/usr/bin/env python3
"""Trusted local coordinator: verify main, review with Astra, sign, dispatch, read back."""
import base64
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

REPOSITORY = 'taehyeonglim/2026-esports-landscape'
STATE = Path(os.environ.get('ASTRA_STATE_DIR', str(Path.home() / '.local/share/esports-astra-review')))

def run(args, cwd, *, data=None, timeout=1800):
    result = subprocess.run(args, cwd=cwd, input=data, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed ({result.returncode}): {result.stdout[-4000:]}')
    return result.stdout

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))

def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()

def utc():
    return dt.datetime.now(dt.timezone.utc)

def main():
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    with (STATE / 'runner.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        repo = STATE / 'repository'
        if not repo.exists():
            run(['git', 'clone', f'https://github.com/{REPOSITORY}.git', str(repo)], STATE)
        run(['git','fetch','origin','main'], repo)
        source = run(['git','rev-parse','origin/main'],repo).strip()
        status_file = STATE / 'status.json'
        previous = json.loads(status_file.read_text()) if status_file.exists() else {}
        if previous.get('source_sha') == source:
            if previous.get('status') in ('deployed', 'rejected'):
                return
            if time.time() - previous.get('attempted_at', 0) < 3600:
                return
        status = {'source_sha':source,'attempted_at':time.time(),'status':'running'}
        def save():
            temporary = status_file.with_suffix('.tmp')
            temporary.write_text(json.dumps(status, indent=2)+'\n')
            temporary.replace(status_file)
        save()
        try:
            run(['git','checkout','--detach',source],repo)
            if run(['git','status','--porcelain','--untracked-files=no'],repo).strip():
                raise RuntimeError('Private clone has tracked modifications; preserve and investigate')
            policy = json.loads((repo/'config/astra-review-policy.v1.json').read_text())
            if not policy['enabled'] or policy['model'] != 'gpt-6-astra':
                raise RuntimeError('Expected enabled GPT-6 Astra policy')
            run(['npm','ci'],repo)
            run(['npx','playwright','install','chromium','firefox','webkit'],repo)
            verification = run(['npm','run','verify:release'],repo,timeout=3600)
            evidence_dir = STATE / 'reviews' / source
            evidence_dir.mkdir(parents=True,exist_ok=True)
            (evidence_dir/'verification.log').write_text(verification)
            run(['node','scripts/astra-screenshots.mjs',str(evidence_dir)],repo)
            manifest = json.loads((repo/'dist/release-manifest.json').read_text())
            evidence = {'source_sha':source,'release_id':manifest['release_id'], 'policy':policy,
                        'verification':'\n'.join(line for line in verification.splitlines() if not line.startswith('[WebServer]'))[-120000:],
                        'screenshots':{name:hashlib.sha256((evidence_dir/f'{name}.png').read_bytes()).hexdigest() for name in ('desktop','mobile','research','typology','detail')}, 'files':{}}
            # Explicit, bounded public inputs only. Never include credentials, private DB or raw source fetches.
            patterns = ['src/*.js','styles/*.css','scripts/astra-*.mjs','automation/*.py']
            paths = [repo/p for p in ['index.html','research/index.html','data/site.v3.json',
                    '.github/workflows/pages.yml','docs/astra-release.md','tests/browser.e2e.mjs','tests/e2e-contract.test.mjs',
                    'scripts/validate-data.mjs','scripts/review-overlay.mjs','scripts/verify-release.mjs']]
            for pattern in patterns:
                paths.extend(sorted(repo.glob(pattern)))
            for path in paths:
                if path.is_file():
                    evidence['files'][str(path.relative_to(repo))] = json.loads(path.read_text()) if path.suffix == '.json' else path.read_text()
            bundle = canonical(evidence)
            if len(bundle.encode()) > 1800000:
                raise RuntimeError('Evidence exceeds bounded review context')
            (evidence_dir/'evidence.json').write_text(bundle)
            prompt = (repo/'automation/astra-review-prompt.md').read_text()+'\n<release_evidence>\n'+bundle+'\n</release_evidence>'
            args = ['codex','exec','--ignore-user-config','--model',policy['model'],'--sandbox','read-only',
                    '--ephemeral','--skip-git-repo-check','--cd',str(evidence_dir),
                    '--output-schema',str(repo/'schemas/astra-review-result.v1.schema.json'),
                    '--output-last-message',str(evidence_dir/'review.json'),
                    '-c','features.shell_tool=false','-c','model_reasoning_effort="high"','--json']
            for name in ('desktop','mobile','research','typology','detail'):
                args += ['--image',str(evidence_dir/f'{name}.png')]
            execution = run(args+['-'],evidence_dir,data=prompt,timeout=1800)
            session = None
            for line in execution.splitlines():
                try:
                    event=json.loads(line)
                    if event.get('type')=='thread.started': session=event['thread_id']
                except (ValueError,KeyError):
                    pass
            if not session: raise RuntimeError('Missing Codex execution identity')
            review=json.loads((evidence_dir/'review.json').read_text())
            if review.get('verdict') != 'approved':
                status.update(status='rejected',review=str(evidence_dir/'review.json'))
                save()
                print('Astra rejected release; see local review.json')
                return
            issued=utc()
            payload={'schema_version':1,'repository':REPOSITORY,'source_sha':source,
                     'release_id':manifest['release_id'],'policy_sha256':sha(canonical(policy)),
                     'evidence_sha256':sha(bundle),'issued_at':issued.isoformat(),
                     'expires_at':(issued+dt.timedelta(seconds=policy['max_age_seconds'])).isoformat(),
                     'model':policy['model'],'reasoning_effort':policy['reasoning_effort'],
                     'transport':policy['transport'],'cli_version':run(['codex','--version'],repo).strip(),
                     'session_id':session,'review':review}
            (evidence_dir/'payload.json').write_text(json.dumps(payload,ensure_ascii=False))
            receipt=evidence_dir/'receipt.json'
            run(['node','scripts/astra-receipt.mjs','sign','--payload',str(evidence_dir/'payload.json'),
                 '--policy','config/astra-review-policy.v1.json','--private',str(STATE/'private.pem'),
                 '--output',str(receipt)],repo)
            run(['node','scripts/astra-receipt.mjs','verify','--receipt',str(receipt),
                 '--policy','config/astra-review-policy.v1.json','--public',str(STATE/'public.pem'),
                 '--source',source,'--release',manifest['release_id']],repo)
            # Never dispatch a superseded main. New main gets a fresh complete review next poll.
            run(['git','fetch','origin','main'],repo)
            if run(['git','rev-parse','origin/main'],repo).strip()!=source:
                raise RuntimeError('main advanced during review; next poll will review new main')
            dispatch_time=utc().isoformat()
            run(['gh','workflow','run','pages.yml','--repo',REPOSITORY,'--ref','main','--json'],repo,
                data=json.dumps({'source_ref':source,'ai_review_receipt':base64.b64encode(receipt.read_bytes()).decode()}))
            run_id=None
            for _ in range(20):
                runs=json.loads(run(['gh','run','list','--repo',REPOSITORY,'--workflow','pages.yml','--event',
                    'workflow_dispatch','--limit','10','--json','databaseId,headSha,createdAt'],repo))
                matching=[r for r in runs if r['headSha']==source and dt.datetime.fromisoformat(r['createdAt'].replace('Z','+00:00'))>=dt.datetime.fromisoformat(dispatch_time)-dt.timedelta(seconds=5)]
                if matching:
                    run_id=matching[0]['databaseId']; break
                time.sleep(3)
            if not run_id: raise RuntimeError('Dispatched run could not be identified')
            status.update(run_id=run_id,review=str(evidence_dir/'review.json'));save()
            run(['gh','run','watch',str(run_id),'--repo',REPOSITORY,'--exit-status','--interval','15'],repo,timeout=3600)
            origin='https://taehyeonglim.github.io/2026-esports-landscape/'
            for attempt in range(12):
                with urllib.request.urlopen(origin+'release-manifest.json?review='+source,timeout=30) as response:
                    live=json.load(response)
                if live.get('release_id')==manifest['release_id']: break
                time.sleep(10)
            else: raise RuntimeError('Live Pages release does not match reviewed release')
            for path in ('','research/','data/site.v3.json'):
                with urllib.request.urlopen(origin+path,timeout=30) as response:
                    if response.status!=200: raise RuntimeError('Live route failed: '+path)
            status.update(status='deployed',release_id=manifest['release_id'],completed_at=utc().isoformat());save()
            print(json.dumps(status))
        except Exception as error:
            status.update(status='error',error=str(error)[-4000:]);save()
            raise

if __name__=='__main__':
    main()
