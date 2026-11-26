"""Prove recorded-only saved processing and missing-source feedback per case."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from source_packet import ASSIGNMENT

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
VALIDATOR = ROOT / '.runtime-work/c110969-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, env):
    return subprocess.run(command, cwd=ROOT, env=env,
                          capture_output=True, text=True)


def log(name, done):
    path = HERE / name
    path.write_text((done.stdout + done.stderr).rstrip() + '\n')
    return path


def prove():
    manifest = json.loads(MANIFEST.read_text())
    scratch = ROOT / '.runtime-work/c229398-recorded-only'
    scratch.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c229398-output')
    env['TMPDIR'] = str(ROOT / '.runtime-work/c229398-tmp')
    Path(env['SCENARIO_PIPELINE_OUTPUT_ROOT']).mkdir(parents=True, exist_ok=True)
    Path(env['TMPDIR']).mkdir(parents=True, exist_ok=True)
    for entry in manifest['cases']:
        case_id = entry['case_id']
        name = case_id.removeprefix(ASSIGNMENT + '__')
        attempt = scratch / (name + '-source')
        if attempt.exists():
            shutil.rmtree(attempt)
        compatibility = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
                         'compatibility', '--manifest', str(MANIFEST),
                         '--case', case_id, '--output', str(attempt),
                         '--library', str(ROOT / 'runtime/library'),
                         '--validator', str(VALIDATOR)]
        source_run = run(compatibility, env)
        if source_run.returncode:
            raise ValueError('fresh selected source compatibility failed: ' +
                             (source_run.stdout + source_run.stderr)[-1500:])
        output = scratch / (name + '-saved')
        if output.exists():
            shutil.rmtree(output)
        command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
                   'process-saved', '--manifest', str(MANIFEST),
                   '--case', case_id, '--attempt', str(attempt),
                   '--output', str(output),
                   '--library', str(ROOT / 'runtime/library'),
                   '--validator', str(VALIDATOR)]
        done = run(command, env)
        positive_log = log('cpu-saved-' + name + '.log', done)
        if done.returncode:
            raise ValueError('recorded-only saved processing failed: ' +
                             positive_log.read_text()[-1500:])
        receipt = json.loads((output / 'v0001/processing.json').read_text())
        if not receipt.get('recorded_only') or not receipt.get('originals_preserved'):
            raise ValueError('saved processing changed original source')
        missing = scratch / (name + '-missing-source')
        if missing.exists():
            shutil.rmtree(missing)
        shutil.copytree(attempt, missing)
        (missing / 'parking_lawfulness.txt').unlink()
        feedback_output = scratch / (name + '-missing-feedback')
        if feedback_output.exists():
            shutil.rmtree(feedback_output)
        feedback_command = command.copy()
        feedback_command[feedback_command.index('--attempt') + 1] = str(missing)
        feedback_command[feedback_command.index('--output') + 1] = str(feedback_output)
        feedback = run(feedback_command, env)
        feedback_log = log('cpu-saved-' + name + '-missing.log', feedback)
        if feedback.returncode:
            raise ValueError('missing saved-source feedback failed: ' +
                             feedback_log.read_text()[-1500:])
        feedback_files = list(feedback_output.glob('v*/feedback.json'))
        if len(feedback_files) != 1:
            raise ValueError('missing saved-source feedback absent')
        state = json.loads(feedback_files[0].read_text())
        if (state.get('recorded_only') is not True or
                state.get('native_replay_requested') is not False):
            raise ValueError('missing source demanded Native replay')
        entry['post_capture'] = {
            'command': ' '.join(command), 'recorded_only': True,
            'diagnostic_fixture': True,
            'test_exit_code': 0, 'test_log': positive_log.name,
            'test_log_sha256': sha(positive_log),
            'feedback_command': ' '.join(feedback_command),
            'feedback_test_exit_code': 0,
            'feedback_log': feedback_log.name,
            'feedback_log_sha256': sha(feedback_log),
            'physical_acceptance_claimed': False}
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return len(manifest['cases'])


if __name__ == '__main__':
    print(prove())
