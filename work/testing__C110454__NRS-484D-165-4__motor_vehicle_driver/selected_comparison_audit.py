"""Pairwise saved parked-headlamp comparison with original-source checks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from selected_delivery_audit import audit as audit_delivery, required, rows

ASSIGNMENT = 'testing__C110454__NRS-484D-165-4__motor_vehicle_driver'
PAIRS = {'lighted_applicability': ('unlit', 'low_beam'),
         'dimmed_vs_bright_headlamp': ('low_beam', 'high_beam')}


def audit(comparison_id: str, left: Path, right: Path, *, diagnostic: bool = False,
          negative_change_fixed: bool = False) -> dict:
    if comparison_id not in PAIRS:
        raise ValueError('unknown exact comparison ID')
    modes = PAIRS[comparison_id]
    roots = (left.resolve(), right.resolve())
    receipts = [audit_delivery(root, ASSIGNMENT + '__' + mode,
                               diagnostic=diagnostic) for root, mode in zip(roots, modes)]
    sites = [json.loads(required(root, 'site-packet.json').read_text()) for root in roots]
    configs = [json.loads(required(root, 'config.json').read_text()) for root in roots]
    actors = [rows(required(root, 'actor-state.jsonl')) for root in roots]
    for site in sites:
        site.pop('case_id', None)
    if negative_change_fixed:
        sites[1]['map_name'] = 'changed-fixed-map'
    if sites[0] != sites[1]:
        raise ValueError('declared fixed condition changed: reviewed site')
    for config in configs:
        config.pop('selected_case_id', None)
        config.pop('requested_headlamp_mode', None)
        config.pop('case', None)
    if configs[0] != configs[1]:
        raise ValueError('declared fixed condition changed: capture configuration')
    expected = {'unlit': 0, 'low_beam': 1, 'high_beam': 2}
    for rows_for_mode, mode in zip(actors, modes):
        if not rows_for_mode or any(row['light_state_bits'] != expected[mode]
                                    for row in rows_for_mode):
            raise ValueError('original light-state readback differs: ' + mode)
        if any(row.get('speed_mps', 1) > .1 or row.get('parking_brake') is not True
               or row.get('footprint_inside_reviewed_parking_polygon') is not True
               for row in rows_for_mode):
            raise ValueError('parked interval differs: ' + mode)
    if [(row['frame'], row['time_s']) for row in actors[0]] != [
            (row['frame'], row['time_s']) for row in actors[1]]:
        raise ValueError('fixed recording timeline changed')
    return {'format': 'parked-headlamp-independent-comparison-v1',
            'comparison_id': comparison_id, 'case_ids': [ASSIGNMENT + '__' + m for m in modes],
            'source_audits': receipts, 'fixed_conditions_confirmed': True,
            'requested_variable_confirmed': True, 'diagnostic_fixture': diagnostic,
            'emitted_intensity_or_aim_proven': False, 'legal_verdict_claimed': False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', required=True)
    parser.add_argument('--right', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    parser.add_argument('--negative-change-fixed', action='store_true')
    args = parser.parse_args()
    result = audit(args.comparison, Path(args.left), Path(args.right),
                   diagnostic=args.diagnostic_fixture,
                   negative_change_fixed=args.negative_change_fixed)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'comparison_id': args.comparison, 'passed': True,
                      'diagnostic': args.diagnostic_fixture}))


if __name__ == '__main__':
    main()
