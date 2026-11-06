"""Pinned runtime offline checks for eight exact, unselected constructions."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

FOLDER=Path(__file__).resolve().parent
ROOT=FOLDER.parents[1]
MANIFEST=FOLDER/'draft-execution-manifest.json'
PYTHON=ROOT/'.venv-cpu/bin/python'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    data=json.loads(MANIFEST.read_text())
    if data['status']!='draft_not_selected' or len(data['cases'])!=2:
        raise ValueError('Only exact unselected two-case draft allowed')
    env=dict(os.environ)
    geos=ROOT/'.runtime-work/geos-wheel/shapely.libs'
    if geos.is_dir():env['LD_LIBRARY_PATH']=str(geos)+os.pathsep+env.get('LD_LIBRARY_PATH','')
    scratch=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c111294-offline-'))
    receipts=[]
    for entry in data['cases']:
        case=entry['case_id'];suffix=case.split('__')[-1]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            output=scratch/(suffix+'-'+candidate)
            command=[str(PYTHON),str(ROOT/'runtime.py'),'offline','--manifest',str(MANIFEST),
                     '--case',case,'--candidate',candidate,'--output',str(output),
                     '--python',str(PYTHON)]
            result=subprocess.run(command,cwd=ROOT,env=env,text=True,
                                  stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
            folder=FOLDER/'draft-candidates'/suffix/candidate
            log=folder/'draft-command.log';log.write_text(result.stdout)
            selection=entry if candidate=='primary' else next(row for row in entry['candidates'] if row['id']==candidate)
            receipt={'case_id':case,'candidate_id':candidate,'command':' '.join(command),
                'exit_code':result.returncode,'command_log':str(log.relative_to(FOLDER)),
                'command_log_sha256':sha(log),'construction_sha256':selection['construction_sha256'],
                'scope':'exact unselected offline CPU check; no Native behavior or acceptance'}
            if (output/'offline.log').is_file():
                unit=folder/'unit-test.log';shutil.copyfile(output/'offline.log',unit)
                receipt.update(unit_log=str(unit.relative_to(FOLDER)),unit_log_sha256=sha(unit))
            (folder/'draft-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
            receipts.append(receipt)
            print(suffix,candidate,'exit',result.returncode,flush=True)
    (FOLDER/'draft-offline-summary.json').write_text(json.dumps({
        'format':'unselected-draft-offline-summary-v1',
        'runtime_manifest_sha256':data['runtime_manifest_sha256'],
        'results':receipts},indent=2)+'\n')
    if any(row['exit_code'] for row in receipts):raise SystemExit(1)

if __name__=='__main__':main()
