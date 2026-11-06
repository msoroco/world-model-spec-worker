"""Pinned runtime.py offline checks for exact unselected truck packages."""
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


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    data=json.loads(MANIFEST.read_text())
    if data.get('status')!='draft_not_selected' or len(data.get('cases',[]))!=7:
        raise ValueError('Only exact unselected seven-case draft allowed')
    env=dict(os.environ)
    geos=ROOT/'.runtime-work/geos-wheel/shapely.libs'
    if geos.is_dir():env['LD_LIBRARY_PATH']=str(geos)+os.pathsep+env.get('LD_LIBRARY_PATH','')
    scratch=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c102372-offline-'))
    receipts=[]
    for entry in data['cases']:
        case=entry['case_id'];suffix=case.rsplit('__',1)[-1]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            output=scratch/(suffix+'-'+candidate)
            command=[str(PYTHON),str(ROOT/'runtime.py'),'offline','--manifest',str(MANIFEST),
                '--case',case,'--candidate',candidate,'--output',str(output),
                '--python',str(PYTHON)]
            result=subprocess.run(command,cwd=ROOT,env=env,text=True,
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
            folder=HERE/'draft-candidates'/suffix/candidate
            log=folder/'draft-command.log';log.write_text(result.stdout)
            ref=entry if candidate=='primary' else next(
                row for row in entry['candidates'] if row['id']==candidate)
            receipt={'case_id':case,'candidate_id':candidate,'exit_code':result.returncode,
                'command':' '.join(command),'command_log':str(log.relative_to(HERE)),
                'command_log_sha256':sha(log),'construction_sha256':ref['construction_sha256'],
                'scope':'exact unselected CPU offline; no Native physical or acceptance claim'}
            if (output/'offline.log').is_file():
                unit=folder/'unit-test.log';shutil.copyfile(output/'offline.log',unit)
                receipt.update(unit_log=str(unit.relative_to(HERE)),unit_log_sha256=sha(unit))
            (folder/'draft-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
            receipts.append(receipt)
            print(suffix,candidate,'exit',result.returncode,flush=True)
    (HERE/'draft-offline-summary.json').write_text(json.dumps({
        'format':'unselected-draft-offline-summary-v1',
        'runtime_manifest_sha256':data['runtime_manifest_sha256'],
        'results':receipts},indent=2)+'\n')
    if any(row['exit_code'] for row in receipts):raise SystemExit(1)


if __name__=='__main__':main()
