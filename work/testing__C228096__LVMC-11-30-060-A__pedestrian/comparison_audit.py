"""Audit exact outside-crosswalk contrasts from saved original source packets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit, required, sha

ROOT = Path(__file__).resolve().parent
FRAME_DIFFERENCES = {'yield_behavior': {'pedestrian_yield_observed'},
    'vehicle_presence': {'vehicles_on_roadway', 'vehicle_positions_xyz_m'},
    'designated_prohibition': set()}
SITE_DIFFERENCES = {'yield_behavior': set(), 'vehicle_presence': set(),
    'designated_prohibition': {'prohibited_place_under_11_30_070'}}


def compare(comparison_id: str, first: Path, second: Path, diagnostic: bool = False) -> dict:
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    declared = next((row for row in plan['comparisons']
        if row['comparison_id'] == comparison_id), None)
    if declared is None or comparison_id not in FRAME_DIFFERENCES:
        raise ValueError('unknown exact outside-crosswalk comparison')
    attempts = [first.resolve(), second.resolve()]
    reports = []
    packets = []
    for attempt, case_id in zip(attempts, declared['case_ids']):
        reports.append(audit(attempt, case_id, diagnostic))
        packets.append(json.loads(required(attempt, 'original-crossing-observations.json').read_text()))
    left, right = packets
    for key in ('assignment_id', 'pedestrian_actor_id', 'site_source_sha256'):
        if left.get(key) != right.get(key):
            raise ValueError('fixed original crossing identity differs: ' + key)
    site_changed = {key for key in set(left['site']) | set(right['site'])
        if left['site'].get(key) != right['site'].get(key)}
    if site_changed != SITE_DIFFERENCES[comparison_id]:
        raise ValueError('declared crossing-site contrast differs')
    if len(left['frames']) != len(right['frames']):
        raise ValueError('comparison original frame counts differ')
    frame_changed = set()
    for a, b in zip(left['frames'], right['frames']):
        frame_changed.update(key for key in set(a) | set(b) if a.get(key) != b.get(key))
        if a.get('frame') != b.get('frame') or a.get('time_s') != b.get('time_s'):
            raise ValueError('comparison original frame/time differs')
    if frame_changed != FRAME_DIFFERENCES[comparison_id]:
        raise ValueError('declared crossing frame contrast differs: ' + str(sorted(frame_changed)))
    if sha(attempts[0] / 'original-crossing-observations.json') == sha(
            attempts[1] / 'original-crossing-observations.json'):
        raise ValueError('comparison reused one original crossing source')
    a, b = [report['measurement'] for report in reports]
    if comparison_id == 'yield_behavior' and not (
            a['pedestrian_yield_observed_at_entry'] and not b['pedestrian_yield_observed_at_entry']
            and a['vehicles_on_roadway_at_entry'] and b['vehicles_on_roadway_at_entry']):
        raise ValueError('pedestrian yield contrast absent')
    if comparison_id == 'vehicle_presence' and not (
            a['vehicles_on_roadway_at_entry'] and not b['vehicles_on_roadway_at_entry']):
        raise ValueError('all-vehicle roadway presence contrast absent')
    if comparison_id == 'designated_prohibition' and not (
            not a['prohibited_place_under_11_30_070']
            and b['prohibited_place_under_11_30_070']):
        raise ValueError('11.30.070 designated-place contrast absent')
    return {'format': 'worker-comparison-audit', 'comparison_id': comparison_id,
        'case_ids': declared['case_ids'], 'passed': True, 'diagnostic_only': diagnostic,
        'physical_acceptance': False, 'legal_acceptance': False,
        'fixed_conditions': declared['fixed_conditions'],
        'deliberate_differences': declared['deliberate_differences'],
        'observed_changed_frame_fields': sorted(frame_changed),
        'observed_changed_site_fields': sorted(site_changed),
        'source_sha256': [sha(attempt / 'original-crossing-observations.json') for attempt in attempts],
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
    result = compare(args.comparison, args.first_attempt, args.second_attempt,
        args.diagnostic_fixture)
    if args.output.exists():
        raise ValueError('retain prior comparison report')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'comparison_id': args.comparison, 'passed': True,
        'diagnostic_only': args.diagnostic_fixture}))


if __name__ == '__main__':
    main()
