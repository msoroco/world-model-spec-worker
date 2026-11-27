"""Synthetic source-shaped motion and lifecycle checker; not Native acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'native'))
from finalize import measure_entry

ORDER = ('capture_finished', 'encoders_closed', 'restoration_verified',
         'native_exit', 'owner_released', 'saved_processing_started')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lifecycle(events):
    if tuple(events) != ORDER:
        raise ValueError('Saved processing precedes Native ownership closure')
    return True


def evaluate(attempt, kind):
    attempt = Path(attempt)
    config = json.loads((attempt / 'config.json').read_text())
    path = attempt / 'private-entry-actors.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('Source-shaped private-way motion incomplete')
    sources = {name: digest(attempt / name) for name in
               ('private-entry-actors.jsonl', 'video_frames.jsonl',
                'private-entry-context.json', 'road.xodr')}
    if kind == 'complete_motion':
        measured = measure_entry(attempt)
        if config['case_id'].endswith('__probe_a'):
            passed = measured['highway_vehicles_before_ego'] == measured['highway_vehicle_count']
        else:
            passed = measured['highway_vehicles_before_ego'] == measured['highway_vehicle_count'] - 1
        if not passed:
            raise ValueError('Source-shaped selected episode did not meet target')
        status, observed = 'met', {'private_way_entry': measured}
        mutation = 'full 600-frame source-shaped episode'
    elif kind == 'incomplete_motion':
        # A short 100-frame observation has no ego highway entry or conflict.
        truncated = rows[:100]
        if any(row['actors']['ego']['body_xy_m'][3][1] >= -4 for row in truncated):
            raise ValueError('Counterfactual short entry unexpectedly reached highway')
        status, observed = 'not_met', {'counterfactual_frames': len(truncated)}
        mutation = 'counterfactual 100-frame source truncation before highway entry'
    elif kind == 'missing_evidence':
        if not path.is_file():
            raise ValueError('Base fixture source absent')
        status, observed = 'unverified', {}
        mutation = 'counterfactual omission of original all-vehicle body source'
    else:
        raise ValueError('Unknown physical fixture')
    return {'case_id': config['case_id'], 'fixture_kind': kind,
            'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
            'original_native_observed': False, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False, 'synthetic_mutation': mutation,
            'physical_checks': {'maneuver': {'status': status,
                'method': 'Source-shaped original-body arrival order plus incomplete and omitted evidence controls',
                'sources': sources}},
            'maneuver_completed': status == 'met',
            'realized_observables': observed}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--attempt')
    p.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence'))
    p.add_argument('--output')
    p.add_argument('--lifecycle', action='store_true')
    a = p.parse_args()
    if a.lifecycle:
        lifecycle(ORDER)
        try:
            lifecycle(ORDER[:-2] + (ORDER[-1], ORDER[-2]))
        except ValueError as error:
            print(str(error))
        else:
            raise AssertionError('Premature saved processing accepted')
        print('Native closure precedes saved processing')
    else:
        result = evaluate(a.attempt, a.kind)
        Path(a.output).write_text(json.dumps(result, indent=2).rstrip() + '\n')
        print(a.kind, result['physical_checks']['maneuver']['status'])
