"""Run all four exact unselected alley v1 compatibility probes."""
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def run():
    env = dict(os.environ)
    env['PATH'] = str(REPO/'.runtime-work/linux_arm64')+os.pathsep+env.get('PATH','')
    env['LD_LIBRARY_PATH'] = str(REPO/'.runtime-work/geos-wheel/shapely.libs')+os.pathsep+env.get('LD_LIBRARY_PATH','')
    for ident in ('primary','fallback1','fallback2','fallback3'):
        command = [sys.executable,str(HERE/'probe-alley-package-v1.py'),
                   '--candidate',ident]
        result = subprocess.run(command,cwd=REPO,env=env,text=True,
                                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                timeout=300)
        (HERE/('alley-package-'+ident+'.log')).write_text(result.stdout)
        print(ident,result.returncode,flush=True)
        if result.returncode:
            raise RuntimeError('Exact alley package failed: '+ident+' '+result.stdout[-1200:])


if __name__=='__main__':
    run()
