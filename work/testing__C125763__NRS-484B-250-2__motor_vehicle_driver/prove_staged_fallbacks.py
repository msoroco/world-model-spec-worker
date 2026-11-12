"""Check staged physical-criterion alternatives through recorded-only CPU flow."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PYTHON = REPO / '.venv-cpu/bin/python'
VALIDATOR = REPO / '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'
SUFFIXES = {
    'primary': 'yield_ego_left_near_time',
    'right': 'yield_ego_right_near_time',
    'separated': 'yield_ego_left_separated',
    'opposite': 'yield_opposite_left_turn',
}


def run(command, log):
    with log.open('w') as stream:
        completed = subprocess.run(command, cwd=REPO, stdout=stream,
                                   stderr=subprocess.STDOUT, check=False)
    if completed.returncode:
        raise ValueError(f'{log.name} failed with exit {completed.returncode}')


def main():
    for prefix, suffix in SUFFIXES.items():
        case_id = ROOT.name + '__' + suffix
        for candidate in ('fallback1', 'fallback2', 'fallback3'):
            stem = f'physical-{prefix}-{candidate}'
            manifest = ROOT / (stem + '-manifest.json')
            attempt = REPO / '.runtime-work' / ('c125763-' + stem + '-compat-v1')
            offline = REPO / '.runtime-work' / ('c125763-' + stem + '-offline-v1')
            saved = REPO / '.runtime-work' / ('c125763-' + stem + '-saved-v1')
            if any(path.exists() for path in (attempt, offline, saved)):
                raise ValueError('Retain prior staged attempt; choose a new proof version: ' + stem)
            common = [str(PYTHON), 'runtime.py']
            run(common + ['offline', '--manifest', str(manifest), '--case', case_id,
                          '--output', str(offline)], ROOT / (stem + '-offline-v1.log'))
            run(common + ['compatibility', '--manifest', str(manifest), '--case', case_id,
                          '--output', str(attempt), '--library', 'runtime/library',
                          '--validator', str(VALIDATOR)],
                ROOT / (stem + '-compat-v1.log'))
            run(common + ['process-saved', '--manifest', str(manifest), '--case', case_id,
                          '--attempt', str(attempt), '--output', str(saved),
                          '--library', 'runtime/library', '--validator', str(VALIDATOR)],
                ROOT / (stem + '-saved-v1.log'))
            processing = json.loads((saved / 'v0001/processing.json').read_text())
            result = json.loads((attempt / 'result.json').read_text())
            if (processing.get('passed') is not True or
                    processing.get('recorded_only') is not True or
                    processing.get('case_id') != case_id or
                    result['physical_checks']['maneuver']['details'].get('criterion') != 'intersection_clearance' or
                    result.get('physical_acceptance_claimed') is not False):
                raise ValueError('Staged fallback physical/saved outcome differs: ' + stem)
            print(json.dumps({'case_id': case_id, 'candidate': candidate,
                              'offline': 'passed', 'compatibility': 'passed',
                              'recorded_only_saved': 'passed',
                              'physical_acceptance_claimed': False}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
