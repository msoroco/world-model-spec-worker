"""Exercise four exact saved-only commands and failure feedback on CPU sources."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
SCRATCH = REPO / '.runtime-work/c111329-bus-post-capture'
MANIFEST = json.loads((FOLDER / 'execution-manifest.json').read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(entry, *, negative=False):
    case = entry['case_id']
    name = case.rsplit('__', 1)[-1]
    source = REPO / '.runtime-work/c111329/proof-v3' / ('compat-' + name)
    assert source.is_dir(), 'Current source-shaped compatibility attempt missing'
    attempt = SCRATCH / (name + '-attempt')
    if not attempt.exists():
        shutil.copytree(source, attempt, copy_function=os.link)
        (attempt / 'candidate-selection.json').unlink(missing_ok=True)
    owner = SCRATCH / (name + '-diagnostic-owner-release.json')
    owner.write_text(json.dumps({
        'event': 'owner_released',
        'operator_attested': True,
        'native_construction_sha256': sha(attempt / 'construction.json'),
        'native_exit_sha256': None,
        'no_resource_operation_performed': True,
    }, indent=2) + '\n')
    output = SCRATCH / (name + ('-negative' if negative else '-saved'))
    env = dict(os.environ)
    env.update({
        'ATTEMPT': str(attempt),
        'SAVED_OUTPUT': str(output),
        'LIBRARY': str(REPO / 'runtime/library'),
        'VALIDATOR': str(REPO / ('.runtime-work/missing-bus-validator' if negative else
                                 '.runtime-work/c110969-decoder/.lake/build/bin/adapterCheck')),
        'OWNER_RELEASE_RECEIPT': str(owner),
        'TMPDIR': str(SCRATCH),
        'SCENARIO_PIPELINE_OUTPUT_ROOT': str(SCRATCH / 'runtime-output'),
        'PYTHONDONTWRITEBYTECODE': '1',
    })
    command = entry['post_capture']['feedback_command' if negative else 'command']
    process = subprocess.run(command, shell=True, cwd=REPO, env=env,
                             capture_output=True, text=True)
    version = output / 'v0001'
    if negative:
        assert process.returncode != 0, 'Missing validator was accepted'
        feedback = json.loads((version / 'feedback.json').read_text())
        assert feedback['case_id'] == case and feedback['recorded_only'] is True
        assert feedback['native_replay_requested'] is False and feedback.get('error')
        return 'actionable failure feedback without Native replay'
    assert process.returncode == 0, (process.stdout + process.stderr)[-2000:]
    receipt = json.loads((version / 'processing.json').read_text())
    assert receipt['case_id'] == case and receipt['passed'] is True
    assert receipt['recorded_only'] is True and receipt['originals_preserved'] is True
    return 'source-shaped saved-only processing passed'


def main():
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    for entry in MANIFEST['cases']:
        print(entry['case_id'].rsplit('__', 1)[-1] + ': ' + run(entry), flush=True)
    first = MANIFEST['cases'][0]
    print(first['case_id'].rsplit('__', 1)[-1] + ': ' + run(first, negative=True), flush=True)
    print('Diagnostic software receipts only; no original physical or legal acceptance')


if __name__ == '__main__':
    main()
