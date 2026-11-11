"""Bind three tested synthetic outcome packets and lifecycle proof to each case."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
manifest = json.loads(MANIFEST.read_text())
output = HERE / 'physical'
output.mkdir(exist_ok=True)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


lifecycle_log = output / 'lifecycle.log'
lifecycle_command = f'.venv-cpu/bin/python work/{HERE.name}/lifecycle_probe.py'
check = subprocess.run([sys.executable, str(HERE / 'lifecycle_probe.py')],
                       cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
lifecycle_log.write_text(check.stdout)
if check.returncode:
    raise ValueError('Lifecycle fixture failed: ' + check.stdout)

for entry in manifest['cases']:
    case = entry['case_id']
    stem = case.split('__')[-1]
    fixtures = []
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        result = output / f'{stem}-{kind}.json'
        log = output / f'{stem}-{kind}.log'
        command = (f'.venv-cpu/bin/python work/{HERE.name}/physical_fixture.py '
                   f'--case {case} --kind {kind} --output work/{HERE.name}/physical/{result.name}')
        process = subprocess.run([sys.executable, str(HERE / 'physical_fixture.py'),
                                  '--case', case, '--kind', kind, '--output', str(result)],
                                 cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        log.write_text(process.stdout)
        if process.returncode:
            raise ValueError(f'{stem} {kind} failed: {process.stdout[-1200:]}')
        fixtures.append({'kind': kind, 'command': command, 'exit_code': 0,
                         'log': str(log.relative_to(HERE)), 'log_sha256': digest(log),
                         'result': str(result.relative_to(HERE)),
                         'result_sha256': digest(result)})
    receipt = output / f'{stem}-proof.json'
    proof = {'construction_sha256': entry['construction_sha256'],
             'fixture_scope': 'Synthetic Native-shaped source and review logic only; no physical or legal finding',
             'fixtures': fixtures,
             'lifecycle': {'events': ['capture_finished', 'encoders_closed',
                                      'restoration_verified', 'native_exit',
                                      'owner_released', 'saved_processing_started'],
                           'exit_code': 0, 'command': lifecycle_command,
                           'log': str(lifecycle_log.relative_to(HERE)),
                           'log_sha256': digest(lifecycle_log),
                           'test_scope': 'Synthetic ordering with negative; actual Native and operator lifecycle require later verification'}}
    receipt.write_text(json.dumps(proof, indent=2) + '\n')
    entry['physical_preparation'] = {'receipt': str(receipt.relative_to(HERE)),
                                     'sha256': digest(receipt)}
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
print('Bound synthetic physical source fixtures for', len(manifest['cases']), 'cases')
