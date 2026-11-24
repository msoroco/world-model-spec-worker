"""Audit four selected source-bound truck comparison pairs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PAIRS = {
    'comparison': ('probe_1', 'probe_2'),
    'comparison_two_lane_exception': ('probe_2', 'two_lane_exception'),
    'comparison_passing': ('passing_hold', 'passing_overtake'),
    'comparison_conditions': ('conditions_steady', 'conditions_lead_brake')}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list:
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(comparison: str, output: Path) -> None:
    suffix = comparison.removeprefix(HERE.name + '__')
    if comparison != HERE.name + '__' + suffix or suffix not in PAIRS:
        raise ValueError('Unknown exact comparison')
    names = PAIRS[suffix]
    roots = [HERE / 'selected-fixture' / name for name in names]
    motion = [rows(root / 'native_samples.jsonl') for root in roots]
    if any(len(part) != 600 for part in motion):
        raise ValueError('Incomplete comparison source')
    if sha(roots[0] / 'camera_context.json') != sha(roots[1] / 'camera_context.json'):
        raise ValueError('Camera policy differs')
    if suffix != 'comparison_two_lane_exception' and sha(roots[0] / 'road.xodr') != sha(roots[1] / 'road.xodr'):
        raise ValueError('Fixed road geometry differs')
    left, right = motion
    first_same = (left[0]['ego']['center_xy_m'] == right[0]['ego']['center_xy_m'] and
                  left[0]['lead']['center_xy_m'] == right[0]['lead']['center_xy_m'])
    checks = {}
    if suffix == 'comparison':
        checks = {'ego_trajectory_fixed': all(a['ego'] == b['ego'] for a, b in zip(left, right)),
                  'lead_initial_station_changed': left[0]['lead']['center_xy_m'][0] != right[0]['lead']['center_xy_m'][0]}
    elif suffix == 'comparison_two_lane_exception':
        context = [json.loads((root / 'following_context.json').read_text()) for root in roots]
        checks = {'truck_trajectories_fixed': left == right,
                  'directional_lane_count_changed': [c['same_direction_lane_count'] for c in context] == [1, 2],
                  'road_source_changed': sha(roots[0] / 'road.xodr') != sha(roots[1] / 'road.xodr')}
    elif suffix == 'comparison_passing':
        checks = {'initial_truck_positions_fixed': first_same,
                  'ego_trajectory_changed': any(a['ego'] != b['ego'] for a, b in zip(left, right)),
                  'lead_trajectory_changed': any(a['lead'] != b['lead'] for a, b in zip(left, right))}
    else:
        context = [json.loads((root / 'following_context.json').read_text()) for root in roots]
        checks = {'initial_truck_positions_fixed': first_same,
                  'lead_event_changed': context[0]['event'] != context[1]['event'],
                  'lead_trajectory_changed': any(a['lead'] != b['lead'] for a, b in zip(left, right))}
    if not all(checks.values()):
        raise ValueError('Selected comparison source differs from planned isolation: ' + str(checks))
    report = {'format': 'c102372-source-comparison-audit-v1', 'comparison_id': comparison,
              'case_ids': [HERE.name + '__' + name for name in names],
              'source_sha256': [{item: sha(root / item) for item in
                                 ('native_samples.jsonl', 'road.xodr', 'camera_context.json')}
                                for root in roots],
              'checks': checks, 'passed': True, 'diagnostic_fixture': True,
              'legal_verdict_claimed': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'comparison': comparison, 'passed': True, 'checks': checks}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit(args.comparison, args.output)
