"""Synthetic 600-frame rail target and lifecycle checks; no Native claim."""
import argparse
import copy
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from measure_rail import measure

AID = HERE.name
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']
VARIANTS = ('space_clear', 'space_short', 'grade_clear', 'grade_deficit',
            'trailing_exact', 'trailing_just_short')


def source(suffix):
    files = json.loads((HERE / ('diagnostic-' + suffix + '.json')).read_text())['files']
    return json.loads(files['rail-context.json']), [
        json.loads(line) for line in files['rail-actors.jsonl'].splitlines()]


def fixture(suffix, kind):
    if suffix not in VARIANTS or kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown rail physical fixture')
    context, rows = source(suffix)
    rows = copy.deepcopy(rows)
    wants_complete_cross = suffix in ('space_clear', 'grade_clear', 'trailing_exact')
    if kind == 'complete_motion':
        if suffix in ('space_short', 'grade_deficit'):
            label = ('opposite_space_observed' if suffix == 'space_short' else
                     'undercarriage_observed')
            for row in rows[151:]:
                row['stop_cause_source'] = label
    elif kind == 'incomplete_motion':
        if wants_complete_cross:
            for row in rows:
                row['vehicle_center_x_m'] = min(row['vehicle_center_x_m'], 15.0)
        else:
            for row in rows[151:]:
                row['vehicle_center_x_m'] = 21.0
    else:
        rows.pop(300)
    try:
        measured = measure(context, rows)
    except ValueError:
        measured = None
    if measured is None:
        status = 'unverified'
    else:
        matches_clearance = measured['trailing_end_reached_15_feet'] == wants_complete_cross
        matches_cause = (suffix not in ('space_short', 'grade_deficit') or
                         measured[('opposite_space_cause_observed_frames' if suffix == 'space_short'
                                   else 'undercarriage_cause_observed_frames')] > 0)
        status = 'met' if matches_clearance and matches_cause else 'not_met'
    return {'format': 'c202465-cpu-physical-fixture-v1', 'case_id': AID + '__' + suffix,
            'kind': kind, 'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True,
            'physical_checks': {'maneuver': {'status': status,
                'method': '600 joined synthetic rail/body frames, 15-foot trailing-end measurement and branch-specific source-shaped stop cause',
                'sources': ['rail-actors.jsonl', 'rail-context.json',
                            'rail-review/rail-geometry.json', 'video_frames.jsonl']}},
            'maneuver_completed': status == 'met',
            'realized_observables': {
                'frames': measured['frame_count'],
                'max_trailing_clearance_m': measured['maximum_trailing_end_clearance_past_reference_rail_m'],
                'space_cause_frames': measured['opposite_space_cause_observed_frames'],
                'grade_cause_frames': measured['undercarriage_cause_observed_frames']}
                if status == 'met' else {},
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--condition', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.kind == 'lifecycle':
        value = {'format': 'c202465-cpu-lifecycle-v1', 'events': EVENTS,
                 'provenance_kind': 'synthetic_fixture',
                 'original_native_executed': False}
    else:
        value = fixture(args.condition, args.kind)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[args.kind]
        if value['physical_checks']['maneuver']['status'] != expected:
            raise ValueError('Physical rail fixture status differs: ' + args.kind)
    Path(args.output).write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'passed': True, 'kind': args.kind,
                      'condition': args.condition, 'physical_or_legal_acceptance': False}))


if __name__ == '__main__':
    main()
