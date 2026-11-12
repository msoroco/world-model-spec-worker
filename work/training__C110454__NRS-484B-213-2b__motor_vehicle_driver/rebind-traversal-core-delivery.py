"""Refresh five independent delivery-audit diagnostic receipts after adapter binding."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
path = HERE / 'execution-manifest.json'
manifest = json.loads(path.read_text())
script = HERE / 'prove-traversal-core-delivery-historical.py'
assert script.is_file()

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

for entry in manifest['cases']:
    suffix = entry['case_id'].rsplit('__', 1)[-1]
    if not suffix.startswith('traversal_'):
        continue
    folder = HERE / 'update039-traversal-core-delivery-case-proofs' / suffix
    folder.mkdir(parents=True, exist_ok=True)
    audit = entry['delivery_acceptance']
    assert audit['script'] == 'delivery_audit.py'
    assert audit['script_sha256'] == sha(HERE / 'delivery_audit.py')
    for negative, label in [(False, 'positive'), (True, 'negative')]:
        command = [sys.executable, str(script), '--case', entry['case_id']]
        if negative:
            command.append('--negative')
        run = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        log = folder / (label + '.log')
        log.write_text(run.stdout + run.stderr)
        if negative:
            assert run.returncode == 1 and 'Delivery construction differs from selected manifest' in log.read_text(), (suffix, label, run.returncode, log.read_text())
            audit['negative_command'] = ' '.join(command)
            audit['negative_exit_code'] = 1
            audit['negative_log'] = str(log.relative_to(HERE))
            audit['negative_log_sha256'] = sha(log)
        else:
            assert run.returncode == 0 and '"source_shape_passed": true' in log.read_text(), (suffix, label, run.returncode, log.read_text())
            audit['command'] = ' '.join(command)
            audit['test_exit_code'] = 0
            audit['test_log'] = str(log.relative_to(HERE))
            audit['test_log_sha256'] = sha(log)
    print(json.dumps({'case': suffix, 'positive': True, 'negative_rejected': True}), flush=True)
path.write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'manifest_sha256': sha(path), 'cases': 2, 'original_native_accepted': False}))
