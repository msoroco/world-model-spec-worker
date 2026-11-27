"""Bind diagnostic physical states and the ordered Native lifecycle."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c312865-nov27/physical-v5'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    env = os.environ.copy()
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/c312865-nov27/output')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONPATH'] = str(REPO / 'runtime/scenario_pipeline')
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(manifest['assignment_id'] + '__')
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'):
            folder = SCRATCH / (suffix + '-' + kind)
            cmd = [sys.executable, str(ROOT / 'physical_probe.py'),
                   '--case', entry['case_id'], '--kind', kind, '--output', str(folder)]
            result = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True)
            log = ROOT / ('physical-' + suffix + '-' + kind + '.log')
            log.write_text((result.stdout + result.stderr).rstrip() + '\n', encoding='utf-8')
            if result.returncode != 0:
                raise RuntimeError(kind + ': ' + log.read_text())
            if kind == 'lifecycle':
                lifecycle = {'events': ['capture_finished', 'encoders_closed',
                                        'restoration_verified', 'native_exit',
                                        'owner_released', 'saved_processing_started'],
                             'exit_code': 0, 'log': log.name, 'log_sha256': digest(log)}
                continue
            result_path = Path(str(folder) + '-result.json')
            copy = ROOT / ('physical-' + suffix + '-' + kind + '.json')
            copy.write_bytes(result_path.read_bytes())
            fixtures.append({'kind': kind, 'command': ' '.join(cmd), 'exit_code': 0,
                             'log': log.name, 'log_sha256': digest(log),
                             'result': copy.name, 'result_sha256': digest(copy)})
        receipt_path = ROOT / ('physical-' + suffix + '-receipt.json')
        write(receipt_path, {'construction_sha256': entry['construction_sha256'],
                             'fixtures': fixtures, 'lifecycle': lifecycle})
        entry['physical_preparation'] = {'receipt': receipt_path.name,
                                         'sha256': digest(receipt_path)}
        write(manifest_path, manifest)
        print('physical proof', suffix, flush=True)


if __name__ == '__main__':
    main()
