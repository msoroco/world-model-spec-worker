"""Run and bind synthetic physical outcomes and cleanup-order unit proofs."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'selected-draft-execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def emit(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(REPO / '.runtime-work'))
manifest = json.loads(MANIFEST.read_text())
for entry in manifest['cases']:
    case = entry['case_id']
    suffix = case.rsplit('__', 1)[-1]
    out = HERE / 'selected-physical' / suffix
    out.mkdir(parents=True, exist_ok=True)
    fixtures = []
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        command = [sys.executable, str(HERE / 'prove_physical_fixture.py'),
                   '--case', case, '--kind', kind]
        run = subprocess.run(command, cwd=REPO, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if run.returncode:
            raise RuntimeError(run.stdout)
        result = json.loads(run.stdout)
        assert result['fixture_kind'] == kind
        result_path = out / f'{kind}.json'
        log_path = out / f'{kind}.log'
        emit(result_path, result)
        log_path.write_text(f'{kind}: status={result["physical_checks"]["maneuver"]["status"]}; '
                            'synthetic unit fixture; no original Native or legal claim\n')
        fixtures.append({'kind': kind, 'command': ' '.join(command),
                         'exit_code': 0, 'log': str(log_path.relative_to(HERE)),
                         'log_sha256': sha(log_path),
                         'result': str(result_path.relative_to(HERE)),
                         'result_sha256': sha(result_path)})
    command = [sys.executable, str(HERE / 'prove_lifecycle.py'), '--case', case]
    run = subprocess.run(command, cwd=REPO, env=env, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if run.returncode:
        raise RuntimeError(run.stdout)
    lifecycle = json.loads(run.stdout)
    log = out / 'lifecycle.log'
    emit(log, lifecycle)
    proof = {'format': 'c422978-selected-physical-cpu-proof-v1',
             'case_id': case, 'construction_sha256': entry['construction_sha256'],
             'fixtures': fixtures, 'lifecycle': {
                 'events': lifecycle['events'], 'command': ' '.join(command),
                 'exit_code': 0, 'log': str(log.relative_to(HERE)),
                 'log_sha256': sha(log)},
             'synthetic_unit_only': True, 'original_native_executed': False,
             'city_sidewalk_verified': False, 'physical_acceptance_claimed': False,
             'legal_verdict': None}
    proof_path = out / 'physical-preparation.json'
    emit(proof_path, proof)
    entry['physical_preparation'] = {
        'receipt': str(proof_path.relative_to(HERE)), 'sha256': sha(proof_path)}
MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
print(sha(MANIFEST))
