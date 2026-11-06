"""Run 24 unselected exact signal bundles with the pinned runtime offline CLI."""
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
    if data['status']!='draft_not_selected' or len(data['cases'])!=6:
        raise ValueError('Only the unselected six-case draft may use this runner')
    env=dict(os.environ)
    geos=str(ROOT/'.runtime-work/geos-wheel/shapely.libs')
    env['LD_LIBRARY_PATH']=geos+os.pathsep+env.get('LD_LIBRARY_PATH','')
    run_root=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c329610-413-offline-'))
    receipts=[]
    for entry in data['cases']:
        suffix=entry['case_id'].split('__')[-1]
        for ident in ('primary','fallback1','fallback2','fallback3'):
            destination=run_root/(suffix+'-'+ident)
            command=[str(PYTHON),str(ROOT/'runtime.py'),'offline','--manifest',str(MANIFEST),
                '--case',entry['case_id'],'--candidate',ident,'--output',str(destination),
                '--python',str(PYTHON)]
            result=subprocess.run(command,cwd=ROOT,env=env,text=True,
                                  stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
            directory=FOLDER/'draft-candidates'/suffix/ident
            command_log=directory/'draft-command.log';command_log.write_text(result.stdout)
            selected=entry if ident=='primary' else next(c for c in entry['candidates'] if c['id']==ident)
            receipt={'case_id':entry['case_id'],'candidate_id':ident,'command':' '.join(command),
                'exit_code':result.returncode,'command_log':str(command_log.relative_to(FOLDER)),
                'command_log_sha256':sha(command_log),
                'construction_sha256':selected['construction_sha256'],
                'scope':'exact unselected draft bundle offline only; no physical or delivery acceptance proof'}
            if (destination/'offline.log').is_file():
                unit_log=directory/'unit-test.log';shutil.copyfile(destination/'offline.log',unit_log)
                receipt.update(unit_log=str(unit_log.relative_to(FOLDER)),
                               unit_log_sha256=sha(unit_log))
            (directory/'draft-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
            receipts.append(receipt)
            print(suffix,ident,'exit',result.returncode,flush=True)
    (FOLDER/'draft-offline-summary.json').write_text(json.dumps({
        'format':'unselected-draft-offline-summary-v1',
        'runtime_manifest_sha256':data['runtime_manifest_sha256'],
        'results':receipts},indent=2)+'\n')
    if any(r['exit_code'] for r in receipts):raise SystemExit(1)


if __name__=='__main__':run()
