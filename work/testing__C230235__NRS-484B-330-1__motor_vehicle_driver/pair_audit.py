"""Audit one selected comparison from two original saved attempts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from comparison_audit import AXES
from delivery_audit import audit as audit_delivery


def audit(plan_path: Path, comparison_id: str, attempts: tuple[Path, Path],
          *, diagnostic_fixture: bool = False) -> dict:
    plan = json.loads(plan_path.read_text())
    matching = [row for row in plan['comparisons'] if row['comparison_id'] == comparison_id]
    if len(matching) != 1 or comparison_id not in AXES:
        raise ValueError('comparison absent from exact plan')
    row = matching[0]
    cases = row['case_ids']
    if len(cases) != 2:
        raise ValueError('comparison must contain two exact cases')
    scenes, ticks = [], []
    for case_id, attempt in zip(cases, attempts):
        stage = attempt / 'original-flagger-source'
        saved = attempt / 'c230235-saved'
        audit_delivery(stage, saved, case_id=case_id,
                       diagnostic_fixture=diagnostic_fixture)
        scenes.append(json.loads((stage / 'source-packet.json').read_text())['scene'])
        ticks.append([json.loads(line) for line in
                      (stage / 'original-ticks.jsonl').read_text().splitlines()])
    left, right = scenes
    axis = AXES[comparison_id]
    if left[axis] == right[axis]:
        raise ValueError('declared comparison axis did not change')
    fixed = set(left) - {'designated', 'marked_construction', 'authorized', 'signal', 'response'}
    if set(left) != set(right) or any(left[name] != right[name] for name in fixed):
        raise ValueError('comparison changed fixed scene source or geometry')
    if any(left[name] != right[name] for name in set(AXES.values()) - {axis}):
        raise ValueError('comparison changed more than one declared case axis')
    if (len(ticks[0]) != len(ticks[1]) or
            any(a['original_frame'] != b['original_frame'] or a['time_s'] != b['time_s']
                for a, b in zip(*ticks))):
        raise ValueError('comparison changed original frame/time alignment')
    if comparison_id in ('flagger_response', 'marked_construction_response') and not any(
            a['vehicle_speed_mps'] != b['vehicle_speed_mps'] for a, b in zip(*ticks)):
        raise ValueError('driver response contrast was not realized')
    return {'format': 'c230235-pair-original-audit-v1', 'comparison_id': comparison_id,
            'case_ids': cases, 'changed_axis': axis, 'original_source_audits_passed': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--attempt-0', type=Path, required=True)
    parser.add_argument('--attempt-1', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('comparison audit output already exists')
    result = audit(args.plan, args.comparison, (args.attempt_0, args.attempt_1),
                   diagnostic_fixture=args.diagnostic_fixture)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(result['comparison_id'])
