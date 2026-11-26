"""Run pinned saved-only processing on ten synthetic selected sweep attempts."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from parking_pose import SWEEP_REQUESTS


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'sweep-manifest-draft.json'
OUTPUT = REPO / '.runtime-work/c150041-sweep-saved-v3'
VALIDATOR = REPO / '.runtime-work/c150041-decoder-v1/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command):
    result = subprocess.run(command, cwd=REPO, env=os.environ, capture_output=True,
                            text=True, timeout=300)
    if result.returncode:
        raise ValueError('pinned saved proof failed: ' + ' '.join(command) + '\n' +
                         result.stdout[-1200:] + result.stderr[-1200:])
    return result


def main():
    if OUTPUT.exists():
        raise ValueError('fresh saved proof root required')
    OUTPUT.mkdir(parents=True)
    manifest = json.loads(MANIFEST.read_text())
    entries = {row['case_id']: row for row in manifest['cases']}
    for suffix in SWEEP_REQUESTS:
        case = ROOT.name + '__' + suffix
        entry = entries[case]
        folder = ROOT / 'diagnostic' / suffix
        source = OUTPUT / suffix / 'compatibility'
        saved = OUTPUT / suffix / 'saved'
        run([sys.executable, str(REPO / 'runtime.py'), 'compatibility',
             '--manifest', str(MANIFEST), '--case', case, '--candidate', 'primary',
             '--output', str(source), '--library', str(REPO / 'runtime/library'),
             '--validator', str(VALIDATOR)])
        selection = json.loads((source / 'candidate-selection.json').read_text())
        if (selection['manifest_sha256'] != sha(MANIFEST) or
                selection['construction_sha256'] != entry['construction_sha256']):
            raise ValueError('saved selected construction differs')
        original_sha = sha(source / 'parking-history.jsonl')
        command = [sys.executable, str(REPO / 'runtime.py'), 'process-saved',
                   '--manifest', str(MANIFEST), '--case', case,
                   '--attempt', str(source), '--output', str(saved),
                   '--library', str(REPO / 'runtime/library'),
                   '--validator', str(VALIDATOR)]
        result = run(command)
        receipt = json.loads((saved / 'v0001/processing.json').read_text())
        if (receipt.get('passed') is not True or receipt.get('recorded_only') is not True or
                receipt.get('missing_evidence') is not False or
                sha(source / 'parking-history.jsonl') != original_sha):
            raise ValueError('saved processing proof differs')
        log = folder / 'cpu-delivery-saved-sweep-v1.log'
        log.write_text(result.stdout.rstrip() + '\n')
        entry['post_capture'] = {'recorded_only': True,
                                 'command': f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved --manifest work/{ROOT.name}/execution-manifest.json --case {case} --attempt "$ATTEMPT" --output "$SAVED_OUTPUT" --library "$LIBRARY" --validator "$VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"',
                                 'feedback_command': f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved --manifest work/{ROOT.name}/execution-manifest.json --case {case} --attempt "$ATTEMPT" --output "$SAVED_OUTPUT" --library "$LIBRARY" --validator "$VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"',
                                 'test_exit_code': 0,
                                 'test_log': log.relative_to(ROOT).as_posix(),
                                 'test_log_sha256': sha(log),
                                 'proof_scope': 'synthetic saved-only CPU fixture; original capture unreviewed'}
        print(suffix, 'saved passed', flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
