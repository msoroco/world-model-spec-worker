"""Prove three source-bound CPU physical outcomes and Native closure per case."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

from parked_lamps import CASES
from source_packet import ASSIGNMENT

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    manifest = json.loads(MANIFEST.read_text())
    if {entry['case_id'] for entry in manifest['cases']} != {
            ASSIGNMENT + '__' + case.name for case in CASES}:
        raise ValueError('selected parked-light physical inventory changed')
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c229398-output')
    env['TMPDIR'] = str(ROOT / '.runtime-work/c229398-tmp')
    Path(env['SCENARIO_PIPELINE_OUTPUT_ROOT']).mkdir(parents=True, exist_ok=True)
    Path(env['TMPDIR']).mkdir(parents=True, exist_ok=True)
    for entry in manifest['cases']:
        name = entry['case_id'].removeprefix(ASSIGNMENT + '__')
        attempt = ROOT / '.runtime-work/c229398-selected-compat' / name / 'primary'
        fixtures = []
        complete = None
        for kind in KINDS:
            output = HERE / f'physical-{name}-{kind}.json'
            command = [str(ROOT / '.venv-cpu/bin/python'), str(HERE / 'physical_probe.py'),
                       '--case', entry['case_id'], '--kind', kind,
                       '--attempt', str(attempt), '--output', str(output)]
            done = subprocess.run(command, cwd=ROOT, env=env,
                                  capture_output=True, text=True)
            log = HERE / f'physical-{name}-{kind}.log'
            log.write_text((done.stdout + done.stderr).rstrip() + '\n')
            if done.returncode:
                raise ValueError(name + '/' + kind + ' physical proof failed: ' +
                                 log.read_text()[-1500:])
            fixture = {'command': ' '.join(command), 'exit_code': 0,
                       'kind': kind, 'log': log.name, 'log_sha256': sha(log),
                       'result': output.name, 'result_sha256': sha(output)}
            fixtures.append(fixture)
            if kind == 'complete_motion':
                complete = fixture
        receipt = {'format': 'worker-physical-preparation',
                   'case_id': entry['case_id'],
                   'construction_sha256': entry['construction_sha256'],
                   'fixtures': fixtures,
                   'scope': 'synthetic CPU protocol only; no physical acceptance',
                   'lifecycle': {'command': complete['command'],
                                 'events': ['capture_finished', 'encoders_closed',
                                            'restoration_verified', 'native_exit',
                                            'owner_released', 'saved_processing_started'],
                                 'exit_code': 0, 'log': complete['log'],
                                 'log_sha256': complete['log_sha256']}}
        path = HERE / f'physical-{name}-receipt.json'
        path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
        entry['physical_preparation'] = {'receipt': path.name, 'sha256': sha(path)}
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return len(manifest['cases']) * len(KINDS)


if __name__ == '__main__':
    print(prove())
