"""Audit exact WALK contrasts from two independently saved source packets."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import audit, required, sha

ROOT = Path(__file__).resolve().parent
DIFFERENCES = {'walk_vs_wait': {'signal_indication'},
    'facing_requirement': {'pedestrian_facing_signal', 'crossing_direction_matches_signal'},
    'separate_driver_duty': {'driver_yield_observed'}}


def compare(comparison_id: str, first: Path, second: Path, diagnostic: bool = False) -> dict:
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    declared = next((row for row in plan['comparisons']
        if row['comparison_id'] == comparison_id), None)
    if declared is None or comparison_id not in DIFFERENCES:
        raise ValueError('unknown exact WALK comparison')
    attempts = [first.resolve(), second.resolve()]
    sources = []
    reports = []
    for attempt, case_id in zip(attempts, declared['case_ids']):
        reports.append(audit(attempt, case_id, diagnostic))
        sources.append(json.loads(required(attempt, 'original-walk-observations.json').read_text()))
    left, right = sources
    fixed = ('assignment_id', 'pedestrian_actor_id', 'crosswalk_id',
        'pedestrian_signal_id', 'site_source_sha256', 'exception_source_sha256')
    if any(left.get(key) != right.get(key) for key in fixed):
        raise ValueError('fixed WALK source identity differs')
    if len(left['frames']) != len(right['frames']):
        raise ValueError('comparison frame counts differ')
    allowed = DIFFERENCES[comparison_id]
    changed = set()
    for a, b in zip(left['frames'], right['frames']):
        for key in set(a) | set(b):
            if a.get(key) != b.get(key):
                changed.add(key)
        if any(a.get(key) != b.get(key) for key in ('frame', 'time_s')):
            raise ValueError('comparison original frame/time differs')
    if changed != allowed:
        raise ValueError('declared WALK contrast differs: ' + str(sorted(changed)))
    if sha(attempts[0] / 'original-walk-observations.json') == sha(
            attempts[1] / 'original-walk-observations.json'):
        raise ValueError('comparison reused one original WALK observation')
    a = reports[0]['measurement']
    b = reports[1]['measurement']
    if comparison_id == 'walk_vs_wait' and not (
            a['walk_permission_conditions_observed'] and not b['walk_permission_conditions_observed']):
        raise ValueError('WALK versus WAIT permission contrast absent')
    if comparison_id == 'facing_requirement' and not (
            a['walk_permission_conditions_observed'] and not b['walk_permission_conditions_observed']):
        raise ValueError('facing signal permission contrast absent')
    if comparison_id == 'separate_driver_duty' and not (
            a['walk_permission_conditions_observed'] and b['walk_permission_conditions_observed']
            and a['driver_yield_observed_at_entry'] and not b['driver_yield_observed_at_entry']):
        raise ValueError('separate vehicle driver duty contrast absent')
    return {'format': 'worker-comparison-audit', 'comparison_id': comparison_id,
        'case_ids': declared['case_ids'], 'passed': True, 'diagnostic_only': diagnostic,
        'physical_acceptance': False, 'legal_acceptance': False,
        'fixed_conditions': declared['fixed_conditions'],
        'deliberate_differences': declared['deliberate_differences'],
        'observed_changed_fields': sorted(changed),
        'source_sha256': [sha(attempt / 'original-walk-observations.json') for attempt in attempts],
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
