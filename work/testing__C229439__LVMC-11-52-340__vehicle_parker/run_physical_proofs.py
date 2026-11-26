"""Retain three physical outcome probes and an ordered lifecycle proof per case."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
PYTHON = REPO / '.venv-cpu/bin/python'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            result = ROOT / ('physical-' + suffix + '-' + kind + '.json')
            log = ROOT / ('physical-' + suffix + '-' + kind + '.log')
            command = [str(PYTHON), str(ROOT / 'physical_probe.py'),
                       '--case', suffix, '--kind', kind, '--output', str(result)]
            process = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
            log.write_text((process.stdout + process.stderr).rstrip() + '\n')
            if process.returncode:
                raise RuntimeError('physical probe failed: ' + log.read_text())
            fixtures.append({'kind': kind, 'command': ' '.join(command),
                             'exit_code': 0, 'log': log.name,
                             'log_sha256': sha(log), 'result': result.name,
                             'result_sha256': sha(result)})
        life_result = ROOT / ('physical-' + suffix + '-lifecycle.json')
        life_log = ROOT / ('physical-' + suffix + '-lifecycle.log')
        command = [str(PYTHON), str(ROOT / 'physical_probe.py'),
                   '--case', suffix, '--kind', 'lifecycle',
                   '--output', str(life_result)]
        process = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
        life_log.write_text((process.stdout + process.stderr).rstrip() + '\n')
        if process.returncode:
            raise RuntimeError('lifecycle probe failed: ' + life_log.read_text())
        lifecycle = json.loads(life_result.read_text())
        lifecycle.update({'command': ' '.join(command),
                          'log': life_log.name, 'log_sha256': sha(life_log)})
        proof = {'format': 'worker-physical-preparation-v1',
                 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'],
                 'fixtures': fixtures, 'lifecycle': lifecycle}
        path = ROOT / ('physical-' + suffix + '-proof.json')
        path.write_text(json.dumps(proof, indent=2) + '\n')
        entry['physical_preparation'] = {'receipt': path.name, 'sha256': sha(path)}
        MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
        print(suffix, 'physical and lifecycle probes passed', flush=True)


if __name__ == '__main__':
    run()
