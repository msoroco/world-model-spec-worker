"""Exercise all exact saved-processing commands and failure feedback on CPU."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
SCRATCH = REPO / '.runtime-work/c136559-post-capture-proof'
MANIFEST_PATH = FOLDER / 'execution-manifest.json'
MANIFEST = json.loads(MANIFEST_PATH.read_text())
VALIDATOR = REPO / '.runtime-work/c150099-decoder-v2/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def environment():
    env = dict(os.environ)
    env.update({
        'TMPDIR': str(SCRATCH / 'tmp'),
        'SCENARIO_PIPELINE_OUTPUT_ROOT': str(SCRATCH / 'runtime-output'),
        'PYTHONDONTWRITEBYTECODE': '1',
    })
    return env


def runtime(*args):
    command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'), *map(str, args)]
    process = subprocess.run(command, cwd=REPO, env=environment(),
                             capture_output=True, text=True, timeout=300)
    assert process.returncode == 0, (process.stdout + process.stderr)[-2000:]


def attempt_for(entry):
    tag = entry['case_id'].rsplit('__', 1)[-1]
    attempt = SCRATCH / (tag + '-attempt')
    fixture = SCRATCH / (tag + '-fixture')
    runtime('materialize', '--manifest', MANIFEST_PATH, '--case', entry['case_id'],
            '--output', attempt)
    runtime('fixture', '--recipe', REPO / entry['fixture_recipe'], '--output', fixture)
    for path in fixture.iterdir():
        destination = attempt / path.name
        assert not destination.exists(), 'Fixture shadows materialized source: ' + path.name
        if path.is_dir():
            shutil.copytree(path, destination, copy_function=os.link)
        else:
            os.link(path, destination)
    (attempt / 'candidate-selection.json').unlink(missing_ok=True)
    owner = SCRATCH / (tag + '-diagnostic-owner-release.json')
    owner.write_text(json.dumps({
        'event': 'owner_released',
        'operator_attested': True,
        'native_construction_sha256': sha(attempt / 'construction.json'),
        'native_exit_sha256': None,
        'no_resource_operation_performed': True,
    }, indent=2) + '\n')
    return attempt, owner


def run(entry, attempt, owner, *, negative=False):
    case = entry['case_id']
    tag = case.rsplit('__', 1)[-1]
    output = SCRATCH / (tag + ('-negative' if negative else '-saved'))
    env = environment()
    env.update({
        'ATTEMPT': str(attempt),
        'PROCESSED': str(output),
        'LEAN_VALIDATOR': str(REPO / '.runtime-work/missing-c136559-validator') if negative else str(VALIDATOR),
        'OWNER_RELEASE_RECEIPT': str(owner),
    })
    command = entry['post_capture']['feedback_command' if negative else 'command']
    process = subprocess.run(command, shell=True, cwd=REPO, env=env,
                             capture_output=True, text=True, timeout=300)
    version = output / 'v0001'
    if negative:
        assert process.returncode != 0, 'Missing validator was accepted: ' + tag
        feedback = json.loads((version / 'feedback.json').read_text())
        assert feedback['case_id'] == case and feedback['recorded_only'] is True
        assert feedback['native_replay_requested'] is False and feedback.get('error')
        return 'actionable failure feedback without Native replay'
    assert process.returncode == 0, (process.stdout + process.stderr)[-2000:]
    receipt = json.loads((version / 'processing.json').read_text())
    assert receipt['case_id'] == case and receipt['passed'] is True
    assert receipt['recorded_only'] is True and receipt['originals_preserved'] is True
    assert receipt['final_video_checks']['passed'] is True
    return 'source-shaped saved-only processing passed'


def main():
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    (SCRATCH / 'tmp').mkdir(parents=True)
    assert VALIDATOR.is_file(), 'Lean validator missing'
    for entry in MANIFEST['cases']:
        tag = entry['case_id'].rsplit('__', 1)[-1]
        attempt, owner = attempt_for(entry)
        print(tag + ': ' + run(entry, attempt, owner), flush=True)
        print(tag + ': ' + run(entry, attempt, owner, negative=True), flush=True)
    print('Diagnostic software receipts only; no original physical or legal acceptance')


if __name__ == '__main__':
    main()
