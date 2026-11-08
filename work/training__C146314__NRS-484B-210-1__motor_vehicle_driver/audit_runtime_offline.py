"""Independently verify pinned offline receipts, materialized bytes and a rejection."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

CASE=Path(__file__).resolve().parent
ROOT=CASE.parents[1]
MANIFEST=CASE/'draft-execution-manifest.json'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def require(ok,message):
    if not ok:raise ValueError(message)


def audit():
    manifest=read(MANIFEST)
    proof=read(CASE/'offline'/'pinned-runtime-proof.json')
    require(proof['manifest_sha256']==sha(MANIFEST) and
            len(proof['entries'])==8 and proof['passed'] is True and
            proof['original_native_observed'] is False and
            proof['delivery_ready'] is False,'pinned proof summary')
    seen=set()
    for row in proof['entries']:
        key=row['case_id'],row['candidate_id']
        require(key not in seen,'duplicate candidate')
        seen.add(key)
        case=next(x for x in manifest['cases'] if x['case_id']==row['case_id'])
        selected=({'construction':case['construction'],
                    'construction_sha256':case['construction_sha256']}
                  if row['candidate_id']=='primary' else
                  next(x for x in case['candidates'] if x['id']==row['candidate_id']))
        source=CASE/selected['construction']
        output=ROOT/row['materialized_dir']
        constructed=read(source)
        choice=read(output/'candidate-selection.json')
        require(sha(source)==selected['construction_sha256']==
                row['construction_sha256']==choice['construction_sha256'] and
                choice['manifest_sha256']==sha(MANIFEST) and
                choice['case_id']==row['case_id'] and
                choice['candidate_id']==row['candidate_id'] and
                row['log_sha256']==sha(output/'offline.log') and
                'Ran 4 tests' in (output/'offline.log').read_text() and
                '\nOK\n' in (output/'offline.log').read_text() and
                row['tests']==4 and row['exit_code']==0 and
                row['simulation_started'] is False,
                'pinned offline command/receipt')
        for item in constructed['files']:
            require((output/item['path']).read_text()==item['content'],
                    'materialized bytes differ')
    require(len(seen)==8,'missing candidate')
    altered=json.loads(MANIFEST.read_text())
    altered['cases'][0]['construction_sha256']='0'*64
    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',dir=CASE,
                                     delete=False) as stream:
        negative=Path(stream.name)
        stream.write(json.dumps(altered)+'\n')
    try:
        with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work') as tmp:
            target=Path(tmp)/'attempt'
            result=subprocess.run([sys.executable,str(ROOT/'runtime.py'),'offline',
                '--manifest',str(negative),'--case',manifest['cases'][0]['case_id'],
                '--candidate','primary','--output',str(target)],cwd=ROOT,
                capture_output=True,text=True,timeout=30)
            require(result.returncode!=0 and
                    'Candidate construction changed' in result.stderr,
                    'changed construction hash accepted')
    finally:
        negative.unlink()
    receipt={'format':'c146314-independent-pinned-offline-audit-v1',
        'materialized_candidates':8,'source_files_verified':
            sum(len(read(CASE/(case['construction'] if candidate=='primary'
                else next(x for x in case['candidates'] if x['id']==candidate)
                    ['construction']))['files'])
                for case in manifest['cases'] for candidate in
                ('primary','fallback1','fallback2','fallback3')),
        'changed_construction_negative_rejected':True,
        'simulation_started':False,'delivery_ready':False}
    (CASE/'offline'/'pinned-runtime-audit.json').write_text(
        json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':print(json.dumps(audit()))
