"""Bind source-shaped CPU physical and lifecycle diagnostics for the lane case."""
import hashlib
import json
import os
import shlex
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PREFIX = HERE.relative_to(REPO)
MANIFEST = HERE / 'execution-manifest.json'
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        run_case(entry)
    write(MANIFEST, manifest)


def run_case(entry):
    suffix = entry['case_id'].split('__')[-1]
    folder = HERE / 'physical-proofs' / suffix
    folder.mkdir(parents=True, exist_ok=True)
    command_tokens = shlex.split(entry['compatibility']['replay_command'])
    source = REPO / command_tokens[command_tokens.index('--output') + 1]
    saved = HERE / entry['post_capture']['test_log']
    receipt = {'format': 'worker-physical-preparation-fixtures', 'case_id': entry['case_id'],
               'construction_sha256': entry['construction_sha256'],
               'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
               'saved_processing_sha256': sha(saved), 'fixtures': []}
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'):
        output = folder / (kind + '.json')
        log = folder / (kind + '.log')
        command = ['.venv-cpu/bin/python', str(PREFIX / 'physical_fixture_proof.py'),
                   '--manifest', str(PREFIX / 'execution-manifest.json'),
                   '--case', entry['case_id'], '--source', str(source.relative_to(REPO)),
                   '--kind', kind, '--output', str(output.relative_to(REPO)),
                   '--saved-receipt', str(saved.relative_to(REPO))]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        result = subprocess.run(command, cwd=REPO, capture_output=True, text=True, env=env)
        log.write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f'{kind} failed: {log.read_text()}')
        item = {'kind': kind, 'command': ' '.join(command), 'exit_code': result.returncode,
                'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                'result': str(output.relative_to(HERE)), 'result_sha256': sha(output)}
        if kind == 'lifecycle':
            item['events'] = json.loads(output.read_text())['events']
            if item['events'] != EVENTS:
                raise ValueError('Lifecycle event order differs')
            receipt['lifecycle'] = item
        else:
            receipt['fixtures'].append(item)
    receipt_path = folder / 'receipt.json'
    write(receipt_path, receipt)
    entry['physical_preparation'] = {'receipt': str(receipt_path.relative_to(HERE)),
                                     'sha256': sha(receipt_path)}
    print(f'{suffix}: met / not_met / unverified and lifecycle passed')


if __name__ == '__main__':
    main()
