"""Run twelve exact unselected synthetic v1 positive/negative probes."""
from pathlib import Path
import os
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SUFFIXES=('below_50_ft','at_50_ft','above_50_ft')
CANDIDATES=('primary','fallback1','fallback2','fallback3')


def main():
    env=dict(os.environ)
    env['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+env.get('PATH','')
    env['LD_LIBRARY_PATH']=str(ROOT/'.runtime-work/geos-wheel/shapely.libs')+os.pathsep+env.get('LD_LIBRARY_PATH','')
    for suffix in SUFFIXES:
        for candidate in CANDIDATES:
            log=HERE/f'package-compatibility-{suffix}-{candidate}.log'
            command=[str(ROOT/'.venv-cpu/bin/python'),str(HERE/'probe-package-compatibility.py'),
                     '--suffix',suffix,'--candidate',candidate]
            with log.open('w') as output:
                result=subprocess.run(command,cwd=ROOT,env=env,stdout=output,
                                      stderr=subprocess.STDOUT,timeout=900)
            print(suffix,candidate,'exit',result.returncode,flush=True)
            if result.returncode:
                print(log.read_text()[-2000:],file=sys.stderr)
                raise SystemExit(result.returncode)


if __name__=='__main__':main()
