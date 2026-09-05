#!/usr/bin/env python3
"""Install the owner-authorized local review scheduler. Credentials stay on this Mac."""
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
state=Path.home()/'.local/share/esports-astra-review'
state.mkdir(parents=True,exist_ok=True,mode=0o700)
os.chmod(state,0o700)
runner=state/'astra-release.py'
shutil.copyfile(Path(__file__).with_name('astra-release.py'),runner)
if not (state/'private.pem').exists():
    subprocess.run(['node',str(Path(__file__).parents[1]/'scripts/astra-receipt.mjs'),'keygen',
                    '--private',str(state/'private.pem'),'--public',str(state/'public.pem')],check=True)
subprocess.run(['gh','variable','set','ASTRA_REVIEW_PUBLIC_KEY','--repo','taehyeonglim/2026-esports-landscape'],
               input=(state/'public.pem').read_text(),text=True,check=True)
label='com.taehyeong.esports-astra-review'
plist=Path.home()/'Library/LaunchAgents'/f'{label}.plist'
plist.parent.mkdir(parents=True,exist_ok=True)
config={'Label':label,'ProgramArguments':[sys.executable,str(runner)],'StartInterval':900,
        'RunAtLoad':True,'WorkingDirectory':str(state),
        'EnvironmentVariables':{'PATH':os.environ['PATH']},
        'StandardOutPath':str(state/'scheduler.log'),'StandardErrorPath':str(state/'scheduler-error.log')}
plist.write_bytes(plistlib.dumps(config))
domain=f'gui/{os.getuid()}'
subprocess.run(['launchctl','bootout',domain,str(plist)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
subprocess.run(['launchctl','bootstrap',domain,str(plist)],check=True)
print(f'Installed {label}; public verification key registered; private key remains local.')
