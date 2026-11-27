"""Independently compare fixed original crossing conditions and declared variables."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit, required, sha

ROOT = Path(__file__).resolve().parent
ALLOWED = {
    'arrival_before_steady': {'in_highway', 'at_destination'},
    'entry_phase': {'in_highway'},
    'curb_destination': {'destination'},
    'safety_zone_destination': {'destination'},
    'other_place_destination': {'destination'},
    'prior_entry_basis': {'countdown_visible', 'in_highway'},
}


def compare(comparison_id: str, first: Path, second: Path, diagnostic: bool = False) -> dict:
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    declared = next((row for row in plan['comparisons']
        if row['comparison_id'] == comparison_id), None)
    if declared is None or comparison_id not in ALLOWED:
        raise ValueError('unknown exact crossing comparison')
    attempts = [first.resolve(), second.resolve()]
    reports = []
    sources = []
    for attempt, cid in zip(attempts, declared['case_ids']):
        reports.append(audit(attempt, cid, diagnostic))
        sources.append(json.loads(required(attempt, 'original-crossing-observations.json').read_text()))
    left, right = sources
    fixed = ('assignment_id', 'pedestrian_actor_id', 'crossing_id',
             'signal_actor_id', 'site_source_sha256', 'signal_source_sha256',
             'destination_source_sha256')
    if any(left.get(key) != right.get(key) for key in fixed):
        raise ValueError('fixed crossing source identity differs')
    if len(left['frames']) != len(right['frames']):
        raise ValueError('crossing comparison frame counts differ')
    changed = set()
    if left['destination'] != right['destination']:
        changed.add('destination')
    for a, b in zip(left['frames'], right['frames']):
        if any(a.get(key) != b.get(key) for key in ('frame', 'time_s')):
            raise ValueError('comparison original frame/time differs')
        changed.update(key for key in set(a) | set(b) if a.get(key) != b.get(key))
    if not changed or not changed <= (ALLOWED[comparison_id] | ({'position_m'} if not diagnostic else set())):
        raise ValueError('declared crossing contrast differs: ' + str(sorted(changed)))
    if comparison_id in ('curb_destination', 'safety_zone_destination', 'other_place_destination'):
        if 'destination' not in changed or (not diagnostic and 'position_m' not in changed):
            raise ValueError('sourced destination route contrast absent')
    elif comparison_id == 'arrival_before_steady':
        if not {'in_highway', 'at_destination'} <= changed:
            raise ValueError('arrival timing contrast absent')
    elif comparison_id == 'entry_phase':
        if 'in_highway' not in changed:
            raise ValueError('first entry phase contrast absent')
    elif comparison_id == 'prior_entry_basis':
        if changed != {'countdown_visible', 'in_highway'}:
            raise ValueError('prior entry and countdown contrast absent')
    if sha(attempts[0] / 'original-crossing-observations.json') == sha(attempts[1] / 'original-crossing-observations.json'):
        raise ValueError('comparison reused one original crossing packet')
    a, b = reports[0]['measurement'], reports[1]['measurement']
    if comparison_id == 'arrival_before_steady' and not (a['arrival_phase'] == 'flashing' and b['arrival_phase'] == 'steady'):
        raise ValueError('arrival before/after steady measurement absent')
    if comparison_id == 'entry_phase' and not (a['entry_phase'] == 'walk' and b['entry_phase'] == 'steady'):
        raise ValueError('Walk versus new-steady entry measurement absent')
    if comparison_id == 'prior_entry_basis' and not (a['entry_phase'] == 'walk' and b['entry_phase'] == 'flashing' and a['countdown_during_flashing'] is False and b['countdown_during_flashing'] is True):
        raise ValueError('no-countdown activation contrast absent')
    return {'format': 'worker-comparison-audit', 'comparison_id': comparison_id,
        'case_ids': declared['case_ids'], 'passed': True,
        'diagnostic_only': diagnostic, 'physical_acceptance': False,
        'legal_acceptance': False, 'fixed_conditions': declared['fixed_conditions'],
        'deliberate_differences': declared['deliberate_differences'],
        'observed_changed_fields': sorted(changed),
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
    result = compare(args.comparison, args.first_attempt, args.second_attempt, args.diagnostic_fixture)
    if args.output.exists():
        raise ValueError('retain prior comparison report')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'comparison_id': args.comparison, 'passed': True,
                      'diagnostic_only': args.diagnostic_fixture}))


if __name__ == '__main__':
    main()
