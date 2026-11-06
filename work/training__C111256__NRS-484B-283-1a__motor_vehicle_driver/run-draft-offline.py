"""Pinned runtime offline proof for sixteen exact, unselected Native bundles."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
FOLDER=Path(__file__).resolve().parent
MANIFEST=FOLDER/'draft-execution-manifest.json'
PYTHON=ROOT/'.venv-cpu/bin/python'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def run():
    data=json.loads(MANIFEST.read_text())
    if data['status']!='draft_not_selected' or len(data['cases'])!=4:
        raise ValueError('Only the four-case unselected draft may run')
    env=dict(os.environ)
    geos=ROOT/'.runtime-work/geos-wheel/shapely.libs'
    if geos.is_dir():
        env['LD_LIBRARY_PATH']=str(geos)+os.pathsep+env.get('LD_LIBRARY_PATH','')
    scratch=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c111256-crosswalk-draft-'))
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
            selected=entry if candidate=='primary' else next(x for x in entry['candidates'] if x['id']==candidate)
            receipt={'case_id':case,'candidate_id':candidate,'command':' '.join(command),
                     'exit_code':result.returncode,'command_log':str(log.relative_to(FOLDER)),
                     'command_log_sha256':sha(log),'construction_sha256':selected['construction_sha256'],
                     'scope':'exact unselected offline bundle; no physical or delivery acceptance proof'}
            source=output/'offline.log'
            if source.is_file():
                unit=folder/'unit-test.log';shutil.copyfile(source,unit)
                receipt.update(unit_log=str(unit.relative_to(FOLDER)),unit_log_sha256=sha(unit))
            (folder/'draft-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
            receipts.append(receipt)
            print(suffix,candidate,'exit',result.returncode,flush=True)
    (FOLDER/'draft-offline-summary.json').write_text(json.dumps({
        'format':'unselected-draft-offline-summary-v1',
        'runtime_manifest_sha256':data['runtime_manifest_sha256'],
        'results':receipts},indent=2)+'\n')
    if any(item['exit_code'] for item in receipts):raise SystemExit(1)

if __name__=='__main__':run()
