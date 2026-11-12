"""Run and bind source-derived synthetic motion and saved lifecycle probes."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log):
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    log.write_text(result.stdout)
    if result.returncode:
        raise ValueError(f'Physical probe failed ({result.returncode}): {log}: {result.stdout[-600:]}')
    return result.returncode


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    output = HERE / 'physical'
    output.mkdir(exist_ok=True)
    for entry in manifest['cases']:
        case = entry['case_id']
        short = case.rsplit('__', 1)[-1]
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            result = output / f'{short}-{kind}.json'
            log = output / f'{short}-{kind}.log'
            command = [sys.executable, str(HERE / 'physical_fixture.py'), '--case', case,
                       '--kind', kind, '--output', str(result)]
            code = run(command, log)
            fixtures.append({'kind': kind, 'command': ' '.join(command), 'exit_code': code,
                             'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                             'result': str(result.relative_to(HERE)), 'result_sha256': sha(result)})
        log = output / f'{short}-lifecycle.log'
        command = [sys.executable, str(HERE / 'lifecycle_fixture.py'), '--case', case]
        code = run(command, log)
        if ' '.join(EVENTS) not in log.read_text():
            raise ValueError('Lifecycle fixture did not report ordered closure: ' + case)
        proof = {'construction_sha256': entry['construction_sha256'],
                 'fixture_scope': 'Synthetic Native-shaped turn source and lifecycle protocol only; no CARLA capture',
                 'fixtures': fixtures, 'lifecycle': {'events': EVENTS, 'exit_code': code,
                    'command': ' '.join(command), 'log': str(log.relative_to(HERE)),
                    'log_sha256': sha(log)}}
        receipt = output / f'{short}-proof.json'
        receipt.write_text(json.dumps(proof, indent=2) + '\n')
        entry['physical_preparation'] = {'receipt': str(receipt.relative_to(HERE)),
                                         'sha256': sha(receipt)}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        path.write_text(json.dumps(manifest, indent=2) + '\n')
        print(short, 'physical and lifecycle CPU protocols passed', flush=True)


if __name__ == '__main__':
    main()
