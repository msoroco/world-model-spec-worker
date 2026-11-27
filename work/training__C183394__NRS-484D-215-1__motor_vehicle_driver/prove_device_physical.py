"""Bind synthetic physical and lifecycle predicates for exact device cases."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
PROBES = ('device_dim', 'device_high')
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


env = dict(os.environ)
env['TMPDIR'] = str(REPO/'.runtime-work/c183394/physical')
env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO/'.runtime-work/c183394/outputs')
env['PYTHONDONTWRITEBYTECODE'] = '1'
for probe in PROBES:
    construction = ROOT/'constructions'/probe/'primary/construction.json'
    receipt = {'format': 'worker-physical-preparation', 'case_id': AID+'__'+probe,
               'construction_sha256': sha(construction), 'fixtures': [],
               'lifecycle': json.loads((ROOT/'native/physical-condition_a-receipt.json').read_text())['lifecycle']}
    for kind in KINDS:
        command = [str(REPO/'.venv-cpu/bin/python'), '-B', str(ROOT/'native/prove_physical.py'),
                   '--case', probe, '--kind', kind]
        result = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
        log = ROOT/'native'/f'physical-{probe}-{kind}.log'
        log.write_text(result.stdout+result.stderr)
        if result.returncode:
            raise RuntimeError(f'{probe} {kind}: {result.stderr[-1000:]}')
        output = ROOT/'native'/f'physical-{probe}-{kind}.json'
        receipt['fixtures'].append({'kind': kind, 'command': ' '.join(command),
            'exit_code': 0, 'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log),
            'result': str(output.relative_to(ROOT)), 'result_sha256': sha(output)})
    destination = ROOT/'native'/f'physical-{probe}-receipt.json'
    destination.write_text(json.dumps(receipt, indent=2)+'\n')
    print('PASS', probe)
