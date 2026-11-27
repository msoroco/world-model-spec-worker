"""Exercise pinned physical completion on explicit diagnostic source mutations."""

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime'))
from scenario_pipeline.worker_exchange.native_output import physical_result


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def run(case, fixture, scratch):
    if case not in ('probe_a', 'probe_b') or fixture not in (
            'complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Select one exact case and physical outcome fixture')
    source = REPO / '.runtime-work/c228508-compat' / (
        'v11-a-primary' if case == 'probe_a' else 'v13-probe_b-primary')
    if scratch.exists():
        raise ValueError('Retain previous fixture run')
    scratch.mkdir(parents=True)
    names = ('config.json', 'video_frames.jsonl', 'trace.jsonl',
             'caravan_history.jsonl', 'caravan_context.json')
    for name in names:
        shutil.copyfile(source / name, scratch / name)
    if fixture == 'incomplete_motion':
        rows = [json.loads(line) for line in (scratch / 'caravan_history.jsonl').read_text().splitlines()]
        for row in rows:
            row['participants']['entrant']['lane_id'] = -2
        (scratch / 'caravan_history.jsonl').write_text(''.join(
            json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
    elif fixture == 'missing_evidence':
        (scratch / 'caravan_history.jsonl').unlink()
    result = json.loads((source / 'result.json').read_text())
    result = physical_result(scratch, result)
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[fixture]
    actual = result['physical_checks']['maneuver']['status']
    if actual != expected or result['maneuver_completed'] != (expected == 'met'):
        raise AssertionError(f'Pinned physical outcome {actual} differs from {expected}')
    target = ROOT / 'selected' / case / 'physical' / (fixture + '-result.json')
    write(target, result)
    print(json.dumps({'case':case,'fixture':fixture,'status':actual,
                      'result_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                      'synthetic_fixture':result['diagnostic_fixture'],
                      'native_claimed':False,'legal_claimed':False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--fixture', required=True)
    parser.add_argument('--scratch', required=True)
    options = parser.parse_args()
    run(options.case, options.fixture, Path(options.scratch).resolve())
