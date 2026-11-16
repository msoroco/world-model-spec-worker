"""Bind CPU-only motion outcome and lifecycle proofs to the draft preview."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
PREVIEW = FOLDER / 'execution-manifest-proof-bound-preview.json'
SCRIPT = FOLDER / 'native/prove_physical_fixture.py'
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path):
    return path.relative_to(FOLDER).as_posix()


def main():
    manifest = json.loads(PREVIEW.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        witness = case.rsplit('__', 1)[-1]
        out = FOLDER / 'proofs/update065' / witness
        out.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in KINDS:
            command = ['.venv-cpu/bin/python', 'work/' + FOLDER.name + '/' + rel(SCRIPT),
                       '--case', case, '--kind', kind]
            process = subprocess.run([str(ROOT / '.venv-cpu/bin/python'), str(SCRIPT),
                                      '--case', case, '--kind', kind],
                                     cwd=ROOT, capture_output=True, text=True)
            log = out / (kind + '.log')
            log.write_text(process.stdout + process.stderr)
            if process.returncode != 0:
                raise RuntimeError(log.read_text())
            value = json.loads(process.stdout)
            assert value['unit_mock'] and not value['original_native_observed']
            assert not value['physical_acceptance_claimed'] and not value['speed_values_supplied']
            result = out / (kind + '.json')
            result.write_text(json.dumps(value, indent=2) + '\n')
            fixtures.append({'kind': kind, 'command': ' '.join(command),
                             'log': rel(log), 'log_sha256': sha(log),
                             'result': rel(result), 'result_sha256': sha(result),
                             'exit_code': 0, 'mock_only': True})
        lifecycle_log = FOLDER / f'update065-{witness}-six-event-lifecycle.log'
        lifecycle = json.loads(lifecycle_log.read_text())
        assert lifecycle['passed'] and lifecycle['mock_only']
        receipt = {'format': 'c146314-physical-preparation-cpu-proof-v1',
                   'case_id': case, 'construction_sha256': entry['construction_sha256'],
                   'fixtures': fixtures,
                   'lifecycle': {'events': lifecycle['events'],
                                 'command': '.venv-cpu/bin/python work/' + FOLDER.name +
                                 '/prove-six-event-lifecycle.py --case ' + case,
                                 'log': rel(lifecycle_log),
                                 'log_sha256': sha(lifecycle_log), 'exit_code': 0,
                                 'mock_only': True},
                   'unit_mock': True, 'original_carla_executed': False,
                   'operator_owner_release_actually_attested': False,
                   'physical_acceptance_claimed': False}
        path = out / 'physical-preparation.json'
        path.write_text(json.dumps(receipt, indent=2) + '\n')
        entry['physical_preparation'] = {'receipt': rel(path), 'sha256': sha(path)}
    PREVIEW.write_text(json.dumps(manifest, indent=2) + '\n')
    sys.path.insert(0, str(ROOT / 'runtime/pipeline'))
    from scenario_pipeline.worker_exchange.physical_preparation import validate
    for entry in manifest['cases']:
        validate(ROOT, FOLDER, entry)
    print(json.dumps({'cases': [e['case_id'] for e in manifest['cases']],
                      'mock_only': True, 'original_native_observed': False,
                      'preview_sha256': sha(PREVIEW)}, sort_keys=True))


if __name__ == '__main__':
    main()
