"""Bind three tested physical outcome branches per selected exact case."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


manifest_path = HERE / 'execution-manifest.json'
manifest = read(manifest_path)
for index, entry in enumerate(manifest['cases'], 1):
    directory = HERE / f'physical-fixtures/controlled_{index}'
    fixtures = []
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        result = directory / f'{kind}.json'
        log = directory / f'{kind}.log'
        assert read(result)['provenance_kind'] == 'synthetic_fixture'
        assert 'cpu_branch_passed' in log.read_text()
        fixtures.append({
            'kind': kind,
            'command': (f'.venv-cpu/bin/python work/{HERE.name}/prove-physical-cpu.py '
                        f'--index {index} --kind {kind} '
                        f'--output work/{HERE.name}/physical-fixtures/controlled_{index}/{kind}.json'),
            'exit_code': 0,
            'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
            'result': str(result.relative_to(HERE)), 'result_sha256': sha(result),
        })
    result = directory / 'lifecycle.json'
    log = directory / 'lifecycle.log'
    lifecycle = {
        'command': (f'.venv-cpu/bin/python work/{HERE.name}/prove-physical-cpu.py '
                    f'--index {index} --kind lifecycle '
                    f'--output work/{HERE.name}/physical-fixtures/controlled_{index}/lifecycle.json'),
        'exit_code': 0,
        'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
        'result': str(result.relative_to(HERE)), 'result_sha256': sha(result),
        'events': read(result)['events'],
    }
    proof = {
        'format': 'worker-roundabout-physical-cpu-v1',
        'case_id': entry['case_id'],
        'construction_sha256': entry['construction_sha256'],
        'script_sha256': sha(HERE / 'prove-physical-cpu.py'),
        'fixtures': fixtures,
        'lifecycle': lifecycle,
        'scope': 'source-hashed synthetic physical outcome and ownership-order CPU test only',
        'physical_or_legal_acceptance': False,
    }
    path = directory / 'proof.json'
    write(path, proof)
    entry['physical_preparation'] = {
        'receipt': str(path.relative_to(HERE)), 'sha256': sha(path),
    }
write(manifest_path, manifest)
print(json.dumps({'manifest_sha256': sha(manifest_path),
                  'proof_sha256': [item['physical_preparation']['sha256']
                                   for item in manifest['cases']]}))
