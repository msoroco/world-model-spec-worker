"""Seal exact synthetic physical outcomes and real Native-owner lifecycle tests."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n')


def prove():
    manifest = json.loads(MANIFEST.read_text())
    lifecycle_command = [str(ROOT / '.venv-cpu/bin/python'), '-m', 'unittest',
                         'discover', '-s', str(HERE / 'tests'), '-p',
                         'test_native_acquisition.py', '-v']
    lifecycle = subprocess.run(lifecycle_command, cwd=ROOT, env=dict(os.environ,
                               PYTHONDONTWRITEBYTECODE='1',
                               SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / '.runtime-work/c230235-owner-nov26b')),
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    lifecycle_log = HERE / 'selected-native-lifecycle.log'
    lifecycle_log.write_text(lifecycle.stdout.rstrip() + '\n')
    if lifecycle.returncode:
        raise ValueError('Native owner lifecycle tests failed: ' + lifecycle.stdout[-1000:])
    for entry in manifest['cases']:
        short = entry['case_id'].removeprefix(HERE.name + '__')
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            result = HERE / ('selected-physical-' + short + '-' + kind + '.json')
            log = HERE / ('selected-physical-' + short + '-' + kind + '.log')
            command = [str(ROOT / '.venv-cpu/bin/python'), str(HERE / 'physical_probe.py'),
                       '--case', entry['case_id'], '--kind', kind, '--output', str(result)]
            completed = subprocess.run(command, cwd=ROOT, env=dict(os.environ,
                                       PYTHONDONTWRITEBYTECODE='1'),
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            log.write_text(completed.stdout.rstrip() + '\n')
            if completed.returncode:
                raise ValueError('physical probe failed: ' + log.read_text()[-1000:])
            fixtures.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                             'log': log.name, 'log_sha256': sha(log),
                             'result': result.name, 'result_sha256': sha(result)})
        receipt = {'format': 'worker-physical-preparation', 'case_id': entry['case_id'],
                   'construction_sha256': entry['construction_sha256'],
                   'scope': 'source-hashed synthetic CPU protocol only', 'fixtures': fixtures,
                   'lifecycle': {'command': ' '.join(lifecycle_command), 'exit_code': 0,
                                 'events': ['capture_finished', 'encoders_closed',
                                            'restoration_verified', 'native_exit',
                                            'owner_released', 'saved_processing_started'],
                                 'log': lifecycle_log.name, 'log_sha256': sha(lifecycle_log)}}
        path = HERE / ('selected-physical-' + short + '-receipt.json')
        write(path, receipt)
        entry['physical_preparation'] = {'receipt': path.name, 'sha256': sha(path)}
        print('physical and lifecycle', short, 'passed', flush=True)
    MANIFEST.write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')


if __name__ == '__main__':
    prove()
