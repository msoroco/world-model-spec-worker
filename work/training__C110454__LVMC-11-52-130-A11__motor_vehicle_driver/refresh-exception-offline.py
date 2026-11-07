"""Refresh pinned offline receipts for all six unselected exception pairs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PYTHON=ROOT/'.venv-cpu/bin/python'
MANIFEST=HERE/'draft-exception-execution-manifest.json'

def main():
    env=dict(os.environ)
    env['LD_LIBRARY_PATH']=str(ROOT/'.runtime-work/geos-wheel/shapely.libs')+os.pathsep+env.get('LD_LIBRARY_PATH','')
    env['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+env.get('PATH','')
    cases=json.loads(MANIFEST.read_text())['cases']
    assert len(cases)==6
    scratch=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='lvmc-exception-offline-'))
    for entry in cases:
        suffix=entry['case_id'].split('__')[-1]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            folder=HERE/'draft-candidates'/suffix/candidate
            output=scratch/(suffix+'-'+candidate)
            run=subprocess.run([str(PYTHON),str(ROOT/'runtime.py'),'offline','--manifest',str(MANIFEST),
                '--case',entry['case_id'],'--candidate',candidate,'--output',str(output),'--python',str(PYTHON)],
                cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
            if run.returncode:raise RuntimeError(suffix+'/'+candidate+': '+run.stdout)
            receipt=json.loads(run.stdout)
            assert receipt['offline_passed'] is True and receipt['simulation_started'] is False
            shutil.copy2(output/'offline.log',folder/'offline.log')
            (folder/'command-offline.log').write_text(json.dumps(receipt,indent=2)+'\n')
            print(suffix,candidate,'offline passed',flush=True)

if __name__=='__main__':main()
