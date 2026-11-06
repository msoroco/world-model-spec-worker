"""Run all eight exact unselected C10316 bundles through pinned offline CLI."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
MANIFEST=HERE/'draft-execution-manifest.json'
PYTHON=ROOT/'.venv-cpu/bin/python'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    data=json.loads(MANIFEST.read_text())
    assert data['status']=='draft_not_selected' and len(data['cases'])==2
    env=dict(os.environ)
    env['LD_LIBRARY_PATH']=str(ROOT/'.runtime-work/geos-wheel/shapely.libs')+os.pathsep+env.get('LD_LIBRARY_PATH','')
    run_root=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c10316-offline-'))
    receipts=[]
    for entry in data['cases']:
        suffix=entry['case_id'].rsplit('__',1)[-1]
        for ident in ('primary','fallback1','fallback2','fallback3'):
            output=run_root/(suffix+'-'+ident)
            command=[str(PYTHON),str(ROOT/'runtime.py'),'offline',
                     '--manifest',str(MANIFEST),'--case',entry['case_id'],
                     '--candidate',ident,'--output',str(output),'--python',str(PYTHON)]
            result=subprocess.run(command,cwd=ROOT,env=env,text=True,
                                  stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
            folder=HERE/'draft-bundles'/suffix/ident
            command_log=folder/'draft-command.log';command_log.write_text(result.stdout)
            selected=entry if ident=='primary' else next(x for x in entry['candidates'] if x['id']==ident)
            receipt={'case_id':entry['case_id'],'candidate_id':ident,
                     'command':' '.join(command),'exit_code':result.returncode,
                     'command_log':str(command_log.relative_to(HERE)),
                     'command_log_sha256':sha(command_log),
                     'construction_sha256':selected['construction_sha256'],
                     'scope':'exact unselected CPU draft offline; no Native execution or delivery acceptance'}
            if (output/'offline.log').is_file():
                unit=folder/'unit-test.log';shutil.copyfile(output/'offline.log',unit)
                receipt.update(unit_log=str(unit.relative_to(HERE)),unit_log_sha256=sha(unit))
            (folder/'draft-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
            receipts.append(receipt)
            print(suffix,ident,'exit',result.returncode,flush=True)
    (HERE/'draft-offline-summary.json').write_text(json.dumps({
        'format':'unselected-draft-offline-summary-v1',
        'runtime_manifest_sha256':data['runtime_manifest_sha256'],
        'results':receipts},indent=2)+'\n')
    if any(row['exit_code'] for row in receipts):raise SystemExit(1)


if __name__=='__main__':main()
