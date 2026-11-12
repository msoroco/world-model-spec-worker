"""Rebind diagnostic candidate selections and run every saved-only choice."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_name(case, candidate):
    if case == 'crosswalk_clear_downstream':
        return 'primary-saved-attempt-current' if candidate == 'primary' else f'{candidate}-saved-attempt-v2'
    if case == 'crosswalk_blocked_downstream':
        return f'blocked-{candidate}-saved-attempt-current'
    return f'{case}-saved-attempt-v1' if candidate == 'primary' else f'{case}-{candidate}-saved-attempt-v1'


def main():
    repo = Path(__file__).resolve().parents[2]
    folder = Path(__file__).resolve().parent
    manifest = folder/'execution-manifest.json'
    stage = repo/'.runtime-work/c382420-stage'
    output = repo/'.runtime-work/c382420-return-saved-all'
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for entry in json.loads(manifest.read_text())['cases']:
        case_id = entry['case_id']
        case = case_id.split('__')[-1]
        for choice in ['primary','fallback1','fallback2','fallback3']:
            name = f'{case}-{choice}'
            src = stage/source_name(case,choice)
            attempt = output/(name+'-attempt')
            dst = output/(name+'-output')
            if attempt.exists() or dst.exists():
                raise ValueError('Retain prior attempt; use a fresh output root')
            shutil.copytree(src,attempt)
            selection = attempt/'candidate-selection.json'
            data = json.loads(selection.read_text())
            data['manifest_sha256'] = sha(manifest)
            selection.write_text(json.dumps(data,indent=2)+'\n')
            command = [sys.executable,str(repo/'runtime.py'),'process-saved',
                       '--manifest',str(manifest),'--case',case_id,'--attempt',str(attempt),
                       '--output',str(dst),'--library',str(repo/'runtime/library'),
                       '--validator',str(repo/'.runtime-work/c125714-validator/.lake/build/bin/adapterCheck')]
            result = subprocess.run(command,cwd=repo,text=True,capture_output=True)
            if result.returncode:
                raise ValueError(name+': '+result.stderr[-1000:])
            receipt = dst/'v0001/processing.json'
            proof = json.loads(receipt.read_text())
            if not (proof['passed'] and proof['recorded_only'] and not proof['missing_evidence'] and
                    proof.get('originals_preserved')):
                raise ValueError(name+': saved proof incomplete')
            rows.append({'case_id':case_id,'candidate_id':choice,'construction_sha256':
                         proof['native_revision']['construction_sha256'],
                         'receipt':str(receipt.relative_to(repo)),'receipt_sha256':sha(receipt),
                         'originals_preserved':True,'physical_acceptance_claimed':False})
            print(name+' passed',flush=True)
    index={'format':'worker-saved-only-diagnostic-proof-index','assignment_id':
           'heldout__C382420__LVMC-11-20-070__motor_vehicle_driver',
           'manifest_sha256':sha(manifest),'cases':rows}
    (folder/'saved-return-proof-index.json').write_text(json.dumps(index,indent=2)+'\n')


if __name__=='__main__':
    main()
