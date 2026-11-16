"""Run and bind the five exact CPU physical/lifecycle preparation receipts."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRIPT = HERE / 'physical_motion_fixture.py'
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def bind():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    script_hash = sha(SCRIPT)
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.split('__')[-1]
        folder = HERE / 'physical-proofs' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        fixtures = []
        lifecycle = None
        for kind in KINDS:
            output = folder / (kind + '.json')
            log = folder / (kind + '.log')
            command = ['.venv-cpu/bin/python', f'work/{HERE.name}/physical_motion_fixture.py',
                       '--case', case, '--kind', kind, '--output',
                       str(output.relative_to(REPO))]
            with log.open('w') as stream:
                run = subprocess.run(command, cwd=REPO, stdout=stream,
                                     stderr=subprocess.STDOUT, check=False)
            if run.returncode:
                raise RuntimeError(f'{case}/{kind} exited {run.returncode}: {log}')
            result = json.loads(output.read_text())
            row = {'command': ' '.join(command), 'exit_code': 0, 'kind': kind,
                   'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                   'result': str(output.relative_to(HERE)), 'result_sha256': sha(output)}
            if kind == 'lifecycle':
                if result.get('events') != EVENTS or not result.get('failed_encoder_rejected'):
                    raise ValueError('Lifecycle closure proof incomplete: ' + case)
                lifecycle = dict(row, events=EVENTS)
            else:
                expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                            'missing_evidence': 'unverified'}[kind]
                observed = result['physical_checks']['maneuver']
                if (observed['status'] != expected or not observed['sources']
                        or result['maneuver_completed'] != (expected == 'met')
                        or result['physical_acceptance_claimed'] is not False):
                    raise ValueError('Physical outcome fixture differs: ' + case + '/' + kind)
                fixtures.append(row)
        receipt = {'format': 'worker-c125697-physical-preparation',
                   'case_id': case, 'construction_sha256': entry['construction_sha256'],
                   'diagnostic_fixture_only': True,
                   'fixture_script': 'physical_motion_fixture.py',
                   'fixture_script_sha256': script_hash,
                   'fixtures': fixtures, 'lifecycle': lifecycle,
                   'physical_acceptance_claimed': False}
        receipt_path = folder / 'receipt.json'
        write(receipt_path, receipt)
        entry['physical_preparation'] = {'receipt': str(receipt_path.relative_to(HERE)),
                                         'sha256': sha(receipt_path)}
        manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
        print(suffix, flush=True)
    return len(manifest['cases'])


if __name__ == '__main__':
    print(json.dumps({'physical_receipts': bind()}))
