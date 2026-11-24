"""Run and bind CPU physical-preparation triads for existing exact cases."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    scratch = args.scratch.resolve()
    manifest_path = folder / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(scratch / 'output')
    env['TMPDIR'] = str(scratch / 'tmp')
    (scratch / 'output').mkdir(parents=True, exist_ok=True)
    (scratch / 'tmp').mkdir(parents=True, exist_ok=True)
    for entry in manifest['cases']:
        case = entry['case_id'].split('__')[-1]
        case_dir = folder / 'cases' / case
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            result = case_dir / ('physical-' + kind + '.json')
            log = case_dir / ('physical-' + kind + '.log')
            command = [sys.executable, str(folder / 'prove_physical.py'),
                       '--case', case, '--kind', kind, '--scratch', str(scratch),
                       '--result', str(result)]
            proc = subprocess.run(command, capture_output=True, text=True, env=env)
            log.write_text((proc.stdout + proc.stderr).rstrip() + '\n')
            if proc.returncode:
                raise RuntimeError(f'{case} {kind}: {proc.returncode}: {log.read_text()}')
            fixtures.append({'kind': kind, 'command': ' '.join(command),
                             'exit_code': 0, 'log': str(log.relative_to(folder)),
                             'log_sha256': sha(log), 'result': str(result.relative_to(folder)),
                             'result_sha256': sha(result)})
        life_log = case_dir / 'physical-lifecycle.log'
        command = [sys.executable, str(folder / 'prove_lifecycle.py'),
                   '--case', case, '--scratch', str(scratch)]
        proc = subprocess.run(command, capture_output=True, text=True, env=env)
        life_log.write_text((proc.stdout + proc.stderr).rstrip() + '\n')
        if proc.returncode:
            raise RuntimeError(f'{case} lifecycle: {proc.returncode}: {life_log.read_text()}')
        events = json.loads(proc.stdout)['events']
        receipt = case_dir / 'physical-preparation.json'
        write_json(receipt, {'format': 'worker-physical-preparation',
                             'construction_sha256': entry['construction_sha256'],
                             'fixtures': fixtures,
                             'lifecycle': {'events': events, 'command': ' '.join(command),
                                           'exit_code': 0,
                                           'log': str(life_log.relative_to(folder)),
                                           'log_sha256': sha(life_log)},
                             'scope': 'Synthetic CPU diagnostic only; no Native physical or legal acceptance.'})
        entry['physical_preparation'] = {'receipt': str(receipt.relative_to(folder)),
                                         'sha256': sha(receipt)}
        print(case, 'physical CPU triad/lifecycle passed', flush=True)
    write_json(manifest_path, manifest)


if __name__ == '__main__':
    main()
