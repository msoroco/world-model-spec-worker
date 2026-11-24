"""Run three synthetic physical-check branches and lifecycle order proof."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from physical_completion import Lifecycle, evaluate


FOLDER = Path(__file__).resolve().parent


def fixture(case, kind):
    polygon = [[0, 0], [10, 0], [10, 10], [0, 10]]
    expected = {'frame_count': 900, 'first_frame': 1, 'case_id': case['case_id'],
                'subject_id': 'synthetic-ego', 'device_id': 'synthetic-device',
                'device_instruction': case['exact_instruction'],
                'parking_polygon': polygon, 'halt_action': case['halt_action']}
    rows = []
    for index in range(900):
        stopped = kind == 'complete_motion' and index >= 400
        rows.append({'frame': index + 1, 'time_s': index * 0.05,
                     'case_id': case['case_id'], 'subject_id': 'synthetic-ego',
                     'device_id': 'synthetic-device',
                     'device_instruction': case['exact_instruction'],
                     'device_effective': case['device_mode'] == 'effective',
                     'prohibited_actions': [case['halt_action']],
                     'halt_activity': case['halt_action'] if stopped else 'travel',
                     'traffic_conflict': stopped and case['exception'] == 'traffic_conflict',
                     'law_direction': stopped and case['exception'] == 'law',
                     'police_direction': stopped and case['exception'] == 'police_direction',
                     'device_direction': stopped and case['exception'] == 'device_direction',
                     'speed_mps': 0.0 if stopped else 2.0,
                     'body_corners_xy': [[1, 1], [2, 1], [2, 2], [1, 2]]})
    if kind == 'missing_evidence':
        rows[500].pop('police_direction')
    result = evaluate(rows, expected)
    result.update(case_id=case['case_id'], provenance_kind='synthetic_fixture',
                  diagnostic_fixture=True, fixture_kind=kind)
    expected_status = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                       'missing_evidence': 'unverified'}[kind]
    if result['physical_checks']['maneuver']['status'] != expected_status:
        raise ValueError('synthetic physical checker branch mismatch')
    return result


def lifecycle():
    good = Lifecycle()
    for event in Lifecycle.EVENTS:
        good.record(event)
    result = good.complete()
    bad = Lifecycle()
    try:
        bad.record('saved_processing_started')
    except ValueError:
        result['rejected_early_saved_processing'] = True
    else:
        raise ValueError('lifecycle accepted early saved processing')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--fixture', choices=('complete_motion', 'incomplete_motion',
                                              'missing_evidence', 'lifecycle'), required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    case = next((item for item in plan['cases'] if item['case_id'] == args.case), None)
    if case is None:
        raise ValueError('unknown exact case')
    result = lifecycle() if args.fixture == 'lifecycle' else fixture(case, args.fixture)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': args.case, 'fixture': args.fixture,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status', 'lifecycle_passed')}))


if __name__ == '__main__':
    main()
