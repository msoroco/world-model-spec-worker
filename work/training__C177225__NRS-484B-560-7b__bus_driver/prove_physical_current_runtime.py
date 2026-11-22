"""Reprove synthetic physical branches against current selected config sources."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'current-runtime-reproof-manifest.json'
PY = ROOT / '.venv-cpu/bin/python'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
life_log = HERE / 'current-runtime-lifecycle-tests.log'
env = os.environ.copy()
env['PYTHONPATH'] = str(HERE) + ':' + str(ROOT / 'runtime/pipeline/scenario_pipeline')
with life_log.open('w') as stream:
    subprocess.run([str(PY), str(HERE / 'test_lifecycle_preparation.py')],
                   cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT,
                   check=True)
if 'OK' not in life_log.read_text():
    raise ValueError('Lifecycle contract tests failed')
for entry in manifest['cases']:
    case_id = entry['case_id']
    case = case_id.removeprefix(HERE.name + '__')
    selected = ROOT / '.runtime-work/c177225-current-matrix' / case / 'primary/compat'
    fixtures = []
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        if kind == 'complete_motion':
            attempt = selected
        else:
            old = ROOT / f'.runtime-work/update068-c177225-{case}-{kind}'
            attempt = ROOT / '.runtime-work/c177225-current-physical' / case / kind
            attempt.mkdir(parents=True, exist_ok=False)
            for item in old.iterdir():
                if item.name != 'config.json':
                    (attempt / item.name).symlink_to(item, target_is_directory=item.is_dir())
            (attempt / 'config.json').symlink_to(selected / 'config.json')
        result_path = HERE / f'current-runtime-{case}-{kind}-physical.json'
        log_path = HERE / f'current-runtime-{case}-{kind}-physical.log'
        command = [str(PY), str(HERE / 'physical_outcome.py'),
                   '--attempt', str(attempt), '--case', case_id,
                   '--output', str(result_path)]
        with log_path.open('w') as stream:
            subprocess.run(command, cwd=ROOT, stdout=stream,
                           stderr=subprocess.STDOUT, check=True)
        result = json.loads(result_path.read_text())
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if (result['physical_checks']['maneuver']['status'] != expected or
                result['provenance_kind'] != 'synthetic_fixture' or
                result['diagnostic_fixture'] is not True or
                result['original_native_observed'] is not False):
            raise ValueError('Physical diagnostic differs: ' + case + '/' + kind)
        fixtures.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': log_path.name, 'log_sha256': sha(log_path),
                         'result': result_path.name, 'result_sha256': sha(result_path),
                         'scope': 'synthetic diagnostic only; no original Native'})
    proof = {'format': 'c177225-physical-preparation-cpu-v2',
             'case_id': case_id, 'construction_sha256': entry['construction_sha256'],
             'fixtures': fixtures,
             'lifecycle': {
                 'events': ['capture_finished', 'encoders_closed', 'restoration_verified',
                            'native_exit', 'owner_released', 'saved_processing_started'],
                 'exit_code': 0, 'log': life_log.name, 'log_sha256': sha(life_log),
                 'scope': 'CPU receipt-ordering test only',
                 'original_owner_released': False},
             'original_native_observed': False,
             'physical_acceptance_claimed': False,
             'legal_verdict_claimed': False}
    path = HERE / f'current-runtime-{case}-physical-preparation.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    entry['physical_preparation'] = {'receipt': path.name, 'sha256': sha(path)}
    complete = HERE / f'current-runtime-{case}-complete_motion-physical.json'
    complete_log = HERE / f'current-runtime-{case}-complete_motion-physical.log'
    entry['diagnostic_physical_outcome'] = {
        'result': complete.name, 'sha256': sha(complete),
        'log': complete_log.name, 'log_sha256': sha(complete_log),
        'scope': 'synthetic fixture measured target; original Native unobserved'}
# Preserve the proof harness manifest fingerprint for the selected matrix.
print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(MANIFEST)}))
