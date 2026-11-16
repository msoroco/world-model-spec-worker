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


def current_manifest_command(command):
    args = shlex.split(command)
    if '--manifest' in args:
        args[args.index('--manifest') + 1] = str(manifest_path)
    return args


manifest = json.loads(manifest_path.read_text())
for case_index, entry in enumerate(manifest['cases']):
    case = entry['case_id']
    label = case.split('__')[-1]
    spec = entry['physical_preparation']
    path = folder / spec['receipt']
    proof = json.loads(path.read_text())
    proof['construction_sha256'] = entry['construction_sha256']
    for fixture in proof['fixtures']:
        command = current_manifest_command(fixture['command'])
        fixture['command'] = shlex.join(command)
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
        command = current_manifest_command(command)
        life['command'] = shlex.join(command)
        if '--saved-receipt' in command:
            target = repo / command[command.index('--saved-receipt') + 1]
            current = repo / f'.runtime-work/c109749-district-selected-v1-{case_index*4:02d}-saved/v0001/processing.json'
            if not current.is_file():
                raise ValueError('Current primary saved receipt missing: '+str(current))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(current.read_bytes())
        subprocess.run(command, cwd=repo, stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    life['log_sha256'] = sha(folder / life['log'])
    life['exit_code'] = 0
    if life.get('result'):
        life['result_sha256'] = sha(folder / life['result'])
    write(path, proof)
    spec['sha256'] = sha(path)
    print(label, 'physical classifier and lifecycle receipts rebound', flush=True)
write(manifest_path, manifest)
result_path = folder / 'result.json'
result = json.loads(result_path.read_text())
for claim in result['tests']:
    log = folder / claim['log']
    if log.is_file():
        claim['sha256'] = sha(log)
write(result_path, result)
