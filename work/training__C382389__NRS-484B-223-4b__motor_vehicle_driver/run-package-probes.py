"""Refresh eight exact unselected synthetic v1 package diagnostics."""
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main():
    env=dict(os.environ)
    env['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+env.get('PATH','')
    env['LD_LIBRARY_PATH']=str(ROOT/'.runtime-work/geos-wheel/shapely.libs')+os.pathsep+env.get('LD_LIBRARY_PATH','')
    for suffix in ('reference','contrast'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            label='package-compatibility-'+suffix+('' if candidate=='primary' else '-'+candidate)
            log=HERE/(label+'.log')
            command=[str(ROOT/'.venv-cpu/bin/python'),str(HERE/'probe-package-compatibility.py'),
                     '--suffix',suffix,'--candidate',candidate]
            with log.open('w') as stream:
                result=subprocess.run(command,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=900)
            print(suffix,candidate,'exit',result.returncode,flush=True)
            if result.returncode:
                print(log.read_text()[-2000:],file=sys.stderr)
                raise SystemExit(result.returncode)


if __name__=='__main__':main()
