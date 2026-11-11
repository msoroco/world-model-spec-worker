"""Rerun physical classifier and lifecycle CPU fixtures after manifest rebinding."""
import hashlib
import json
import shlex
import subprocess
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent
manifest_path = folder / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


manifest = json.loads(manifest_path.read_text())
for entry in manifest['cases']:
    case = entry['case_id']
    label = case.split('__')[-1]
    spec = entry['physical_preparation']
    path = folder / spec['receipt']
    proof = json.loads(path.read_text())
    proof['construction_sha256'] = entry['construction_sha256']
    for fixture in proof['fixtures']:
        command = shlex.split(fixture['command'])
        with (folder / fixture['log']).open('w') as log:
            subprocess.run(command, cwd=repo, stdout=log, stderr=subprocess.STDOUT, check=True)
        fixture['log_sha256'] = sha(folder / fixture['log'])
        fixture['result_sha256'] = sha(folder / fixture['result'])
        fixture['exit_code'] = 0
    life = proof['lifecycle']
    command = life.get('command')
    if not command:
        source = f'work/{folder.name}/physical_fixture_proof.py'
        output = ('physical-proofs/primary/lifecycle.json' if label == 'reciprocal_yield_after_turn'
                  else 'physical-proofs/reciprocal_continues/lifecycle.json')
        command = (f'.venv-cpu/bin/python {source} --manifest work/{folder.name}/execution-manifest.json '
                   f'--case {case} --kind lifecycle --output work/{folder.name}/{output}')
        life['command'] = command
        life['fixture_receipt'] = output
    with (folder / life['log']).open('w') as log:
        subprocess.run(shlex.split(command), cwd=repo, stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    life['log_sha256'] = sha(folder / life['log'])
    life['exit_code'] = 0
    if life.get('result'):
        life['result_sha256'] = sha(folder / life['result'])
    write(path, proof)
    spec['sha256'] = sha(path)
    print(label, 'physical classifier and lifecycle receipts rebound', flush=True)
write(manifest_path, manifest)
