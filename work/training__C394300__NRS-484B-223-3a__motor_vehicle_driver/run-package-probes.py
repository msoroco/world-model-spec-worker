"""Rerun both controlled cases and four exact unselected v1 candidates."""
from pathlib import Path
import os
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main():
    env=dict(os.environ)
    env['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+env.get('PATH','')
    env['LD_LIBRARY_PATH']=str(ROOT/'.runtime-work/geos-wheel/shapely.libs')+os.pathsep+env.get('LD_LIBRARY_PATH','')
    for case in ('controlled_1','controlled_2'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            log=HERE/f'probe-package-{case}-{candidate}.log'
            command=[str(ROOT/'.venv-cpu/bin/python'),str(HERE/'probe-package-compatibility.py'),
                     '--case',case,'--candidate',candidate]
            with log.open('w') as output:
                result=subprocess.run(command,cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,
                                      timeout=900)
            print(case,candidate,'exit',result.returncode,flush=True)
            if result.returncode:
                print(log.read_text()[-2000:],file=sys.stderr)
                raise SystemExit(result.returncode)


if __name__=='__main__':main()
