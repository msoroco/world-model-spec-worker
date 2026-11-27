"""Test saved-only processing from newly materialized diagnostic acquisitions."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c229023-owner-nov26'
VALIDATOR = REPO / '.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, output):
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH), TMPDIR=str(SCRATCH),
               MPLCONFIGDIR=str(SCRATCH / 'mpl'))
    with output.open('w') as stream:
        completed = subprocess.run(command, cwd=REPO, env=env, stdout=stream,
                                   stderr=subprocess.STDOUT, text=True)
    if completed.returncode:
        raise ValueError(f'Saved CPU command failed: {output}: {output.read_text()[-1500:]}')


def main():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(ROOT.name + '__')
        compatibility = (SCRATCH / 'compat-same-lane-primary-v4' if suffix == 'same_lane_pass'
                         else SCRATCH / f'compat-{suffix}-primary-proof')
        proof = json.loads((compatibility / 'compatibility.json').read_text())
        attempt = SCRATCH / f'saved-source-{suffix}'
        output = SCRATCH / f'saved-replay-{suffix}'
        for path in (attempt, output):
            if path.exists():
                shutil.rmtree(path)
        materialize = [sys.executable, 'runtime.py', 'materialize', '--manifest',
                       str(manifest_path), '--case', case, '--output', str(attempt)]
        run(materialize, SCRATCH / f'saved-materialize-{suffix}.log')
        for name in proof['fixture_manifest']:
            source = compatibility / name
            destination = attempt / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        for name in ('raw.mkv', 'four-view-receipt.json'):
            shutil.copyfile(compatibility / name, attempt / name)
        process = [sys.executable, 'runtime.py', 'process-saved', '--manifest',
                   str(manifest_path), '--case', case, '--attempt', str(attempt),
                   '--output', str(output), '--library', 'runtime/library',
                   '--validator', str(VALIDATOR)]
        raw_log = SCRATCH / f'saved-process-{suffix}-stdout.log'
        run(process, raw_log)
        version = output / 'v0001'
        receipt = json.loads((version / 'processing.json').read_text())
        if (receipt.get('passed') is not True or receipt.get('recorded_only') is not True or
                receipt.get('originals_preserved') is not True or
                receipt.get('missing_evidence') is not False or
                receipt.get('physical_acceptance_claimed') is not False or
                receipt.get('case_id') != case):
            raise ValueError('Saved processing receipt lacks full diagnostic proof')
        log = ROOT / 'cases' / suffix / 'proof-saved-process.log'
        log.write_text(json.dumps({
            'case_id': case, 'passed': True, 'recorded_only': True,
            'originals_preserved': True, 'timestamp_joins': receipt['timestamp_joins'],
            'full_final_decode': bool(receipt['final_video_checks']),
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False,
        }, sort_keys=True) + '\n')
        command = (f'.venv-cpu/bin/python runtime.py process-saved --manifest '
                   f'work/{ROOT.name}/execution-manifest.json --case {case}'
                   ' --attempt "$ATTEMPT" --output "$OUTPUT"'
                   ' --library runtime/library --validator "$VALIDATOR"'
                   ' --owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
        entry['post_capture'] = {
            'recorded_only': True, 'command': command,
            'feedback_command': command,
            'test_log': str(log.relative_to(ROOT)), 'test_log_sha256': sha(log),
            'test_exit_code': 0,
            'scope': 'Synthetic recorded-only CPU replay; original Native pixel and physical review pending',
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
        print(suffix, 'saved-only processing passed', flush=True)


if __name__ == '__main__':
    main()
