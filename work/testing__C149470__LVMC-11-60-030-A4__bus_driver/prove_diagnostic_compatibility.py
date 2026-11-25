"""Positive offline and missing-source negative checks for every exact bundle."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from bus_curb import CASES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c149470'


def run():
    receipts = []
    for case in CASES:
        positive = SCRATCH / ('offline-' + case.name)
        if not (positive / 'offline.log').is_file():
            raise ValueError('pinned positive offline proof missing: ' + case.name)
        check = subprocess.run([sys.executable, 'runner.py', '--check'],
                               cwd=positive, capture_output=True, text=True,
                               timeout=30)
        if check.returncode or 'diagnostic CPU check passed' not in check.stdout:
            raise ValueError('positive bundle check failed: ' + case.name)
        negative = SCRATCH / ('negative-scene-' + case.name)
        if negative.exists():
            shutil.rmtree(negative)
        shutil.copytree(positive, negative)
        (negative / 'scene.json').unlink()
        missing = subprocess.run([sys.executable, 'runner.py', '--check'],
                                 cwd=negative, capture_output=True, text=True,
                                 timeout=30)
        if missing.returncode == 0 or 'scene.json' not in missing.stderr:
            raise ValueError('missing exact scene source was accepted: ' + case.name)
        receipts.append({'case_id': HERE.name + '__' + case.name,
                         'positive_offline': True,
                         'missing_scene_rejected': True,
                         'source_kind': 'synthetic_diagnostic_fixture',
                         'pinned_runtime_compatibility_receipt': False,
                         'physical_acceptance': False})
    target = HERE / 'diagnostic-compatibility-checks.json'
    target.write_text(json.dumps({'format': 'c149470-diagnostic-checks-v1',
                                  'checks': receipts}, indent=2) + '\n')
    return len(receipts)


if __name__ == '__main__':
    print('diagnostic positive/negative checks:', run())
