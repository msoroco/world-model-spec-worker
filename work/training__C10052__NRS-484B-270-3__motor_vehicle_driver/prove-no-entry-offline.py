"""Pinned offline proof for four exact no-entry candidate constructions."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
MANIFEST=HERE/'draft-no-entry-execution-manifest.json'
PYTHON=REPO/'.venv-cpu/bin/python'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=json.loads(MANIFEST.read_text())
    entry=manifest['cases'][0]
    env=dict(os.environ)
    env['LD_LIBRARY_PATH']=str(REPO/'.runtime-work/geos-wheel/shapely.libs')+os.pathsep+env.get('LD_LIBRARY_PATH','')
    receipts=[]
    with tempfile.TemporaryDirectory(dir=REPO/'.runtime-work',prefix='c10052-no-entry-offline-') as temp:
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            ref=entry if candidate=='primary' else next(x for x in entry['candidates'] if x['id']==candidate)
            output=Path(temp)/candidate
            command=[str(PYTHON),str(REPO/'runtime.py'),'offline','--manifest',str(MANIFEST),
                     '--case',entry['case_id'],'--candidate',candidate,'--output',str(output),'--python',str(PYTHON)]
            result=subprocess.run(command,cwd=REPO,env=env,text=True,stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT,timeout=300)
            folder=HERE/'draft-no-entry-candidates'/'probe_d_no_entry'/candidate
            log=folder/'offline.log';log.write_text(result.stdout)
            unit_log=folder/'unit-test.log'
            if (output/'offline.log').is_file():
                shutil.copyfile(output/'offline.log',unit_log)
            else:
                raise RuntimeError('Pinned offline unit log missing: '+candidate)
            receipts.append({'candidate':candidate,'construction_sha256':ref['construction_sha256'],
                             'exit_code':result.returncode,'log_sha256':sha(log),
                             'unit_log_sha256':sha(unit_log),
                             'passed_tests':int(re.search(r'Ran (\d+) tests?',unit_log.read_text()).group(1))})
            if result.returncode:
                raise RuntimeError('Exact no-entry offline failed: '+candidate+'\n'+result.stdout[-2000:])
    proof={'format':'c10052-no-entry-exact-offline-proof-v1','passed':True,
           'manifest_sha256':sha(MANIFEST),'candidates':receipts,
           'selected':False,'physical_observation_claimed':False}
    (HERE/'no-entry-offline-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


if __name__=='__main__':
    result=main()
    print(json.dumps({'passed':result['passed'],'candidates':len(result['candidates']),
                      'tests':[x['passed_tests'] for x in result['candidates']]},indent=2))
