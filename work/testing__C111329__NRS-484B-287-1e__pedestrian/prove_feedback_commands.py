"""Exercise each production saved-processing command on diagnostic sources."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
SCRATCH = REPO / '.runtime-work/c111329-feedback-proof'
MANIFEST = json.loads((FOLDER / 'execution-manifest.json').read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def execute(entry, suffix, *, invalid_validator=False):
    case = entry['case_id']
    source = REPO / '.runtime-work/c111329-selected-runtime' / (suffix + '-saved-source')
    assert source.is_dir(), 'Selected diagnostic source is missing: ' + str(source)
    receipt = SCRATCH / (suffix + '-diagnostic-owner-release.json')
    receipt.write_text(json.dumps({
        'event': 'owner_released',
        'operator_attested': True,
        'native_construction_sha256': digest(source / 'construction.json'),
        'native_exit_sha256': None,
        'no_resource_operation_performed': True,
    }, indent=2) + '\n')
    output = SCRATCH / (suffix + ('-negative' if invalid_validator else '-saved'))
    env = dict(os.environ)
    env.update({
        'ATTEMPT': str(source),
        'SAVED_OUTPUT': str(output),
        'LIBRARY': str(REPO / 'runtime/library'),
        'VALIDATOR': str(REPO / ('.runtime-work/absent-validator' if invalid_validator else
                                 '.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck')),
        'OWNER_RELEASE_RECEIPT': str(receipt),
        'TMPDIR': str(SCRATCH),
        'SCENARIO_PIPELINE_OUTPUT_ROOT': str(SCRATCH / 'runtime-output'),
        'PYTHONDONTWRITEBYTECODE': '1',
    })
    completed = subprocess.run(entry['post_capture']['feedback_command'], shell=True,
                               cwd=REPO, env=env, capture_output=True, text=True)
    version = output / 'v0001'
    if invalid_validator:
        assert completed.returncode != 0, 'Missing validator was accepted'
        feedback = json.loads((version / 'feedback.json').read_text())
        assert feedback['case_id'] == case
        assert feedback['recorded_only'] is True
        assert feedback['native_replay_requested'] is False
        assert feedback.get('error'), 'Failure feedback lacks an actionable error'
        return 'failure feedback generated from saved sources without Native replay'
    assert completed.returncode == 0, (completed.stdout + completed.stderr)[-2000:]
    processing = json.loads((version / 'processing.json').read_text())
    assert processing['case_id'] == case
    assert processing['passed'] is True and processing['recorded_only'] is True
    assert processing['originals_preserved'] is True
    return 'saved-only processing passed with owner-release binding'


def main():
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    for entry in MANIFEST['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        print(suffix + ': ' + execute(entry, suffix))
    first = MANIFEST['cases'][0]
    print(first['case_id'].rsplit('__', 1)[-1] + ': ' +
          execute(first, first['case_id'].rsplit('__', 1)[-1], invalid_validator=True))
    print('Diagnostic receipts only; no original physical acceptance claimed')


if __name__ == '__main__':
    main()
