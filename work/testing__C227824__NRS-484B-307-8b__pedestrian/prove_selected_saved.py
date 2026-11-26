"""Prove selected recorded-only processing and missing-device feedback."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
SCRATCH = REPO / '.runtime-work/c227824-selected-saved'
VALIDATOR = REPO / '.runtime-work/c229439-validator/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, env):
    return subprocess.run(command, cwd=REPO, env=env, capture_output=True,
                          text=True, timeout=600)


def log(name, done):
    path = HERE / name
    path.write_text((done.stdout + done.stderr).rstrip() + '\n')
    return path


def prove():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ)
    env['TMPDIR'] = str(REPO / '.runtime-work/c227824-selected-tmp')
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/c227824-selected-output')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    for entry in manifest['cases']:
        cid = entry['case_id']
        suffix = cid.removeprefix(HERE.name + '__')
        attempt = SCRATCH / (suffix + '-source')
        fixture = SCRATCH / (suffix + '-fixture')
        for path in (attempt, fixture):
            if path.exists():
                shutil.rmtree(path)
        source_command = [sys.executable, str(REPO / 'runtime.py'), 'materialize',
                          '--manifest', str(MANIFEST), '--case', cid,
                          '--output', str(attempt)]
        materialized = run(source_command, env)
        if materialized.returncode:
            raise ValueError(cid + ' selected materialization failed: ' +
                             (materialized.stdout + materialized.stderr)[-1000:])
        fixture_command = [sys.executable, str(REPO / 'runtime.py'), 'fixture',
                           '--recipe', str(REPO / entry['fixture_recipe']),
                           '--output', str(fixture)]
        generated = run(fixture_command, env)
        if generated.returncode:
            raise ValueError(cid + ' selected fixture failed: ' +
                             (generated.stdout + generated.stderr)[-1000:])
        for source in fixture.iterdir():
            target = attempt / source.name
            if target.exists():
                raise ValueError('selected fixture shadows exact construction')
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copyfile(source, target)
        output = SCRATCH / suffix
        if output.exists():
            shutil.rmtree(output)
        command = [sys.executable, str(REPO / 'runtime.py'), 'process-saved',
                   '--manifest', str(MANIFEST), '--case', cid,
                   '--attempt', str(attempt), '--output', str(output),
                   '--library', str(REPO / 'runtime/library'),
                   '--validator', str(VALIDATOR)]
        done = run(command, env)
        positive = log('cpu-selected-saved-' + suffix + '.log', done)
        if done.returncode:
            raise ValueError(cid + ' saved positive failed: ' + positive.read_text()[-1500:])
        response = json.loads(done.stdout)
        if (response.get('passed') is not True or
                response.get('recorded_only') is not True or
                response.get('originals_preserved') is not True or
                response.get('physical_acceptance_claimed') is not False):
            raise ValueError(cid + ' saved processing claim differs')
        missing = SCRATCH / (suffix + '-missing-source')
        if missing.exists():
            shutil.rmtree(missing)
        shutil.copytree(attempt, missing)
        (missing / 'device-history.jsonl').unlink()
        feedback_output = SCRATCH / (suffix + '-feedback')
        if feedback_output.exists():
            shutil.rmtree(feedback_output)
        negative_command = command.copy()
        negative_command[negative_command.index('--attempt') + 1] = str(missing)
        negative_command[negative_command.index('--output') + 1] = str(feedback_output)
        negative = run(negative_command, env)
        feedback_log = log('cpu-selected-saved-' + suffix + '-missing.log', negative)
        if negative.returncode:
            raise ValueError(cid + ' missing source feedback failed: ' + feedback_log.read_text()[-1500:])
        feedback_files = list(feedback_output.glob('v*/feedback.json'))
        if len(feedback_files) != 1:
            raise ValueError(cid + ' missing feedback file')
        feedback = json.loads(feedback_files[0].read_text())
        if feedback.get('recorded_only') is not True or feedback.get('native_replay_requested') is not False:
            raise ValueError(cid + ' requested Native replay after missing evidence')
        entry['post_capture'] = {'recorded_only': True,
                                 'command': ' '.join(command),
                                 'test_exit_code': 0,
                                 'test_log': positive.name,
                                 'test_log_sha256': sha(positive),
                                 'feedback_command': ' '.join(negative_command),
                                 'feedback_test_exit_code': 0,
                                 'feedback_log': feedback_log.name,
                                 'feedback_log_sha256': sha(feedback_log),
                                 'diagnostic_fixture': True,
                                 'physical_acceptance_claimed': False}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    return len(manifest['cases'])


if __name__ == '__main__':
    print(prove())
