"""Build exact-case synthetic physical and lifecycle CPU receipts."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
SCRIPT = ROOT / 'native/prove_physical.py'
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


manifest = json.loads(MANIFEST.read_text())
for entry in manifest['cases']:
    suffix = entry['case_id'].split('__')[-1]
    attempt = SCRATCH / ('attempt-' + suffix + '-final')
    proof_dir = ROOT / 'native/proofs' / suffix / 'physical'
    proof_dir.mkdir(parents=True, exist_ok=True)
    receipts = []
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        result = proof_dir / (kind + '.json')
        log = proof_dir / (kind + '.log')
        command = [sys.executable, '-B', str(SCRIPT), '--attempt', str(attempt),
                   '--kind', kind, '--output', str(result)]
        run = subprocess.run(command, capture_output=True, text=True)
        if run.returncode:
            raise RuntimeError(kind + ': ' + run.stderr)
        log.write_text(run.stdout.rstrip() + '\n')
        receipts.append({'kind':kind,'command':' '.join(command),
            'exit_code':0,'log':str(log.relative_to(ROOT)),'log_sha256':sha(log),
            'result':str(result.relative_to(ROOT)),'result_sha256':sha(result)})
    life_log = proof_dir / 'lifecycle.log'
    life_command = [sys.executable, '-B', str(SCRIPT), '--lifecycle']
    run = subprocess.run(life_command, capture_output=True, text=True)
    if run.returncode:
        raise RuntimeError(run.stderr)
    life_log.write_text(run.stdout.rstrip() + '\n')
    proof = {'format':'c229422-synthetic-physical-proof-v1',
        'case_id':entry['case_id'],'construction_sha256':entry['construction_sha256'],
        'original_native_observed':False,'diagnostic_only':True,'fixtures':receipts,
        'lifecycle':{'events':['capture_finished','encoders_closed','restoration_verified',
            'native_exit','owner_released','saved_processing_started'],
            'exit_code':0,'negative_premature_saved_processing_rejected':True,
            'log':str(life_log.relative_to(ROOT)),'log_sha256':sha(life_log)}}
    path = proof_dir / 'proof.json';write(path,proof)
    entry['physical_preparation']={'receipt':str(path.relative_to(ROOT)),'sha256':sha(path)}
write(MANIFEST,manifest)
print('four exact synthetic physical/lifecycle receipts generated')
