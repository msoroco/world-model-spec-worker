"""Run three synthetic physical outcomes per exact case and bind CPU receipts."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
NAMES = ('near_centerline', 'farther_from_centerline',
         'imaginary_near_centerline', 'imaginary_farther_from_centerline')
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean_log(path, content):
    lines = [line.rstrip(' \t') for line in content.splitlines()]
    Path(path).write_text('\n'.join(lines).rstrip('\n') + ('\n' if lines else ''))


def build():
    scratch = REPO / '.runtime-work/c109705-2b-nov24/physical'
    scratch.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TMPDIR=str(scratch), PYTHONDONTWRITEBYTECODE='1',
               PYTHONPATH=str(REPO / 'runtime'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(scratch / 'pipeline'))
    lifecycle_log = HERE / 'cpu-physical-lifecycle-tests.log'
    command = [str(REPO / '.venv-cpu/bin/python'), '-m', 'unittest',
               'discover', '-s', str(HERE / 'tests'), '-p', 'test_capture_lifecycle.py', '-v']
    test = subprocess.run(command, cwd=REPO, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    clean_log(lifecycle_log, test.stdout)
    if test.returncode:
        raise ValueError('capture lifecycle tests failed')
    for name in NAMES:
        case = HERE.name + '__' + name
        folder = HERE / 'cases' / name / 'physical'
        folder.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in KINDS:
            result = folder / (kind + '.json')
            log = folder / (kind + '.log')
            workdir = scratch / (name + '-' + kind)
            if workdir.exists() or result.exists():
                raise ValueError('Use fresh physical proof outputs')
            args = [str(REPO / '.venv-cpu/bin/python'), str(HERE / 'physical_fixture.py'),
                    '--case', case, '--kind', kind, '--scratch', str(workdir),
                    '--result', str(result)]
            test = subprocess.run(args, cwd=REPO, env=env, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            clean_log(log, test.stdout)
            if test.returncode:
                raise ValueError(f'{name} {kind} physical proof failed')
            fixtures.append({'kind': kind,
                             'command': ' '.join(args), 'exit_code': 0,
                             'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                             'result': str(result.relative_to(HERE)),
                             'result_sha256': sha(result)})
        construction = HERE / ('construction-' + name + '.json')
        receipt = {'format': 'c109705-physical-preparation-cpu-v1',
                   'case_id': case, 'construction_sha256': sha(construction),
                   'fixtures': fixtures,
                   'lifecycle': {'events': EVENTS, 'exit_code': 0,
                                 'log': lifecycle_log.name,
                                 'log_sha256': sha(lifecycle_log),
                                 'scope': 'synthetic CPU lifecycle test only'}}
        (folder / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(name, 'three physical outcomes passed')


if __name__ == '__main__':
    build()
