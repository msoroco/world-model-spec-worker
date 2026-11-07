"""Run all twenty exact unselected synthetic v1 positive/negative probes."""
from pathlib import Path
import os
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SUFFIXES=('witness_1','witness_2','numeric_1_0','numeric_1_1','numeric_1_2')
CANDIDATES=('primary','fallback1','fallback2','fallback3')


def main():
    env=dict(os.environ)
    env['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+env.get('PATH','')
    env['LD_LIBRARY_PATH']=str(ROOT/'.runtime-work/geos-wheel/shapely.libs')+os.pathsep+env.get('LD_LIBRARY_PATH','')
    for suffix in SUFFIXES:
        for candidate in CANDIDATES:
            name='package-compatibility-'+suffix+('' if candidate=='primary' else '-'+candidate)+'.log'
            log=HERE/name
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
