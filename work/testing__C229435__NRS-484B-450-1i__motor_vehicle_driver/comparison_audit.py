"""Independently audit three exact saved nearest-rail contrasts."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from delivery_audit import audit, required, sha

ROOT = Path(__file__).resolve().parent
PAIRS = {'fifty_foot_boundary': ('inside_no_exception', 'boundary_no_exception'),
         'outside_boundary': ('inside_no_exception', 'outside_no_exception'),
         'traffic_conflict_exception': ('inside_no_exception', 'inside_other_vehicle_unresolved')}


def compare(comparison_id: str, first: Path, second: Path, diagnostic: bool = False) -> dict:
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    declared = next((row for row in plan['comparisons'] if row['comparison_id'] == comparison_id), None)
    if declared is None or comparison_id not in PAIRS:
        raise ValueError('unknown exact nearest-rail comparison')
    if tuple(cid.split('__')[-1] for cid in declared['case_ids']) != PAIRS[comparison_id]:
        raise ValueError('declared exact case pair changed')
    attempts = [first.resolve(), second.resolve()]
    reports = [audit(attempt, cid, diagnostic) for attempt, cid in zip(attempts, declared['case_ids'])]
    packets = [json.loads(required(attempt, 'original-rail-observations.json').read_text()) for attempt in attempts]
    left, right = packets
    for key in ('assignment_id', 'vehicle_actor_id', 'vehicle_action', 'rail_polylines_m'):
        if left.get(key) != right.get(key):
            raise ValueError('fixed railroad or ego identity differs: ' + key)
    for key in ('railroad_identity', 'carrier_provenance', 'other_vehicle_actor_id'):
        if left['site'].get(key) != right['site'].get(key):
            raise ValueError('fixed reviewed railroad/other vehicle differs: ' + key)
    if len(left['frames']) != len(right['frames']):
        raise ValueError('comparison original frame counts differ')
    for a, b in zip(left['frames'], right['frames']):
        if (a['other_vehicle_actor_id'] != b['other_vehicle_actor_id'] or
                math.dist(a['other_vehicle_xyz_m'], b['other_vehicle_xyz_m']) > .5 or
                abs(a['other_vehicle_speed_mps'] - b['other_vehicle_speed_mps']) > .5):
            raise ValueError('fixed other-vehicle trajectory differs')
    if sha(attempts[0] / 'original-rail-observations.json') == sha(attempts[1] / 'original-rail-observations.json'):
        raise ValueError('comparison reused one original rail source')
    distances = [r['measurement']['nearest_rail_distance_m'] for r in reports]
    traffic = [p['exception_context']['traffic_conflict_necessity'] for p in packets]
    other_exceptions = ('law_compliance', 'officer_direction', 'official_device_direction')
    if any(left['exception_context'][name] != right['exception_context'][name] for name in other_exceptions):
        raise ValueError('fixed statutory exception context differs')
    if comparison_id == 'fifty_foot_boundary':
        valid = distances[0] < 15.24 and abs(distances[1] - 15.24) <= .25 and traffic == ['absent', 'absent']
    elif comparison_id == 'outside_boundary':
        valid = distances[0] < 15.24 and distances[1] > 15.24 and traffic == ['absent', 'absent']
    else:
        valid = abs(distances[0] - distances[1]) <= .25 and traffic == ['absent', 'unresolved']
    if not valid:
        raise ValueError('declared nearest-rail or traffic-necessity contrast absent')
    return {'format': 'worker-comparison-audit', 'comparison_id': comparison_id,
        'case_ids': declared['case_ids'], 'passed': True, 'diagnostic_only': diagnostic,
        'physical_acceptance': False, 'legal_acceptance': False,
        'fixed_conditions': declared['fixed_conditions'],
        'deliberate_differences': declared['deliberate_differences'],
        'measured_nearest_rail_distances_m': distances,
        'traffic_conflict_necessity_statuses': traffic,
        'source_sha256': [sha(attempt / 'original-rail-observations.json') for attempt in attempts],
        'frame_counts': [report['frame_count'] for report in reports]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--first-attempt', type=Path, required=True)
    parser.add_argument('--second-attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    args = parser.parse_args()
    for source in (args.first_attempt, args.second_attempt):
        if args.output.resolve() == source.resolve() or source.resolve() in args.output.resolve().parents:
            raise ValueError('comparison report must be outside original attempt')
    result = compare(args.comparison, args.first_attempt, args.second_attempt, args.diagnostic_fixture)
    if args.output.exists():
        raise ValueError('retain prior comparison report')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'comparison_id': args.comparison, 'passed': True,
        'diagnostic_only': args.diagnostic_fixture}))


if __name__ == '__main__':
    main()
