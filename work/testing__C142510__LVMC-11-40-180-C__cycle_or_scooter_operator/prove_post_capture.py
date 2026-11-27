"""Exercise six exact recorded-only saved commands and failure feedback."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
SCRATCH = REPO / '.runtime-work/c142510-post-capture-proof'
SOURCE = REPO / '.runtime-work/c142510-owner'
VALIDATOR = SOURCE / 'validator/.lake/build/bin/adapterCheck'
MANIFEST = json.loads((FOLDER / 'execution-manifest.json').read_text())
SOURCE_BY_CASE = {
    'bicycle_signal_before_yield': 'compat-final-primary-bicycle_signal_before_yield',
    'bicycle_signal_late_yield': 'production-compat3-bicycle_signal_late_yield',
    'bicycle_silent_yield': 'compat-final-primary-bicycle_silent_yield',
    'bicycle_signal_before_advance': 'compat-final-primary-bicycle_signal_before_advance',
    'electric_bicycle_signal_before_yield': 'compat-final-primary-electric_bicycle_signal_before_yield',
    'electric_scooter_signal_before_yield': 'compat-final-primary-electric_scooter_signal_before_yield',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(entry, *, negative=False):
    case = entry['case_id']
    tag = case.rsplit('__', 1)[-1]
    source = SOURCE / SOURCE_BY_CASE[tag]
    assert source.is_dir(), 'Current source-shaped compatibility attempt missing: ' + tag
    selected = json.loads((FOLDER / entry['construction']).read_text())
    assert json.loads((source / 'construction.json').read_text()) == selected, 'Stale construction: ' + tag
    attempt = SCRATCH / (tag + '-attempt')
    if not attempt.exists():
        shutil.copytree(source, attempt, copy_function=os.link)
        (attempt / 'candidate-selection.json').unlink(missing_ok=True)
    owner = SCRATCH / (tag + '-diagnostic-owner-release.json')
    owner.write_text(json.dumps({
        'event': 'owner_released',
        'operator_attested': True,
        'native_construction_sha256': sha(attempt / 'construction.json'),
        'native_exit_sha256': None,
        'no_resource_operation_performed': True,
    }, indent=2) + '\n')
    output = SCRATCH / (tag + ('-negative' if negative else '-saved'))
    env = dict(os.environ)
    env.update({
        'ATTEMPT': str(attempt),
        'PROCESSED': str(output),
        'LEAN_VALIDATOR': str(REPO / '.runtime-work/missing-c142510-validator') if negative else str(VALIDATOR),
        'OWNER_RELEASE_RECEIPT': str(owner),
        'TMPDIR': str(SCRATCH),
        'SCENARIO_PIPELINE_OUTPUT_ROOT': str(SCRATCH / 'runtime-output'),
        'PYTHONDONTWRITEBYTECODE': '1',
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
    SCRATCH.mkdir(parents=True)
    assert VALIDATOR.is_file(), 'Lean validator missing'
    for entry in MANIFEST['cases']:
        tag = entry['case_id'].rsplit('__', 1)[-1]
        print(tag + ': ' + run(entry), flush=True)
        print(tag + ': ' + run(entry, negative=True), flush=True)
    print('Diagnostic software receipts only; no original physical or legal acceptance')


if __name__ == '__main__':
    main()
