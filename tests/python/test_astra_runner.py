import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location('astra_runner', ROOT/'automation/astra-release.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

class AstraRunnerTests(unittest.TestCase):
    def exercise(self, fail_verification=False):
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory)
            repo=state/'repository'
            for sub in ('config','automation','dist'):
                (repo/sub).mkdir(parents=True)
            (repo/'config/astra-review-policy.v1.json').write_text((ROOT/'config/astra-review-policy.v1.json').read_text())
            (repo/'automation/astra-review-prompt.md').write_text('Review evidence')
            (repo/'dist/release-manifest.json').write_text(json.dumps({'release_id':'b'*64}))
            calls=[]
            def fake(args, cwd, **kwargs):
                calls.append(args)
                if args[:2]==['git','rev-parse']: return 'a'*40
                if args[:3]==['npm','run','verify:release']:
                    if fail_verification: raise RuntimeError('verification failed')
                    return 'All gates passed'
                if args[:2]==['node','scripts/astra-screenshots.mjs']:
                    for name in ('desktop','mobile','research','typology','detail'): (Path(args[2])/f'{name}.png').write_bytes(b'fixture')
                if args[:2]==['codex','exec']:
                    self.assertIn('gpt-6-astra',args)
                    self.assertIn('features.shell_tool=false',args)
                    self.assertIn('--ignore-user-config',args)
                    self.assertIn('model_reasoning_effort="high"',args)
                    Path(args[args.index('--output-last-message')+1]).write_text(json.dumps({'verdict':'rejected'}))
                    return '{"type":"thread.started","thread_id":"test"}'
                return ''
            with patch.object(runner,'STATE',state), patch.object(runner,'run',side_effect=fake):
                if fail_verification:
                    with self.assertRaisesRegex(RuntimeError,'verification failed'): runner.main()
                else:
                    runner.main()
                count=len(calls)
                runner.main()  # same rejected SHA or transient failure backoff must not rerun expensive work
                self.assertEqual(len(calls),count+2)
            self.assertFalse(any(call[0]=='gh' for call in calls))
            self.assertFalse(any('sign' in call for call in calls))
            self.assertEqual(json.loads((state/'status.json').read_text())['status'],'error' if fail_verification else 'rejected')
    def test_model_rejection_never_signs_or_dispatches(self): self.exercise()
    def test_verification_failure_stops_before_model(self): self.exercise(True)
