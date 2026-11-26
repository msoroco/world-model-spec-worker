"""Reproducible, source-hashed 600-frame CPU diagnostic matrix."""
import hashlib
import json
from pathlib import Path

from measure_lane_change import FRAMES, RATE, measure, read_trace

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]
ASSIGNMENT = ROOT / 'inputs' / PACKAGE.name / 'assignment.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(name):
    rows = []
    for i in range(FRAMES):
        departing = i >= 200
        offset = min(1.8, (i - 180) * 0.03) if i >= 180 else 0.0
        rows.append({
            'source_kind': 'synthetic_native_sample',
            'native_frame': 2000 + i, 'video_frame': i, 'time_s': i / RATE,
            'same_direction_marked_lane_count': 2 if name != 'one_lane' else 1,
            'occupied_lane_half_width_m': 1.75, 'ego_body_half_width_m': 0.9,
            'ego_lateral_offset_from_occupied_lane_center_m': offset,
            'target_direction_indicator_requested_on': i >= (100 if name != 'late_signal' else 260),
            'target_direction_indicator_observed_on': i >= (101 if name != 'late_signal' else 261),
            'target_lane_min_surface_gap_m': 4.0 if name == 'small_gap' else (24.0 if departing else 30.0),
            'target_lane_closing_speed_mps': 8.0 if departing else 0.0,
        })
    return rows


def check_fixture(name, rows):
    frame = 170
    action = 'skipped' if name == 'no_check' else 'evaluated'
    return [{
        'source_kind': 'synthetic_native_sample',
        'native_frame': rows[frame]['native_frame'], 'video_frame': frame,
        'action': action,
        'sampled_target_lane_gap_m': rows[frame]['target_lane_min_surface_gap_m'] if action == 'evaluated' else None,
        'engineering_rule_id': 'controller-gap-check-v1' if action == 'evaluated' else None,
        'decision_to_depart': (name != 'small_gap') if action == 'evaluated' else None,
        'legal_threshold_claimed': False,
    }]


def main():
    expected_input = json.loads((PACKAGE / 'result.json').read_text())['input_sha256']
    if sha(ASSIGNMENT) != expected_input:
        raise ValueError('Frozen assignment binding changed')
    out = HERE / 'diagnostics'
    out.mkdir(exist_ok=True)
    observations = {}
    for name in ('early_signal', 'late_signal', 'small_gap', 'one_lane', 'no_check'):
        trace = out / (name + '.jsonl')
        trace.write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in fixture(name)))
        check_path = out / (name + '-check.jsonl')
        check_path.write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in check_fixture(name, read_trace(trace))))
        result = measure(read_trace(trace), 'synthetic_native_sample', read_trace(check_path))
        observations[name] = dict(result, trace_path=str(trace.relative_to(PACKAGE)),
                                  trace_sha256=sha(trace), check_path=str(check_path.relative_to(PACKAGE)),
                                  check_sha256=sha(check_path))
    assert observations['early_signal']['signal_precedes_departure']
    assert not observations['late_signal']['signal_precedes_departure']
    assert observations['early_signal']['activation_observed']
    assert not observations['one_lane']['activation_observed']
    assert observations['small_gap']['gap_at_departure_m'] < observations['early_signal']['gap_at_departure_m']
    assert observations['small_gap']['controller_decision_to_depart'] is False
    assert observations['early_signal']['controller_decision_to_depart'] is True
    assert observations['no_check']['controller_check_action'] == 'skipped'
    assert all(o['driver_safety_ascertainment'] == 'unobserved' for o in observations.values())
    rejected = []
    for defect in ('missing_frame', 'missing_gap', 'shifted_time',
                   'missing_check', 'stale_check', 'requested_not_observed'):
        rows = fixture('early_signal')
        check_rows = check_fixture('early_signal', rows)
        if defect == 'missing_frame':
            rows.pop()
        elif defect == 'missing_gap':
            del rows[250]['target_lane_min_surface_gap_m']
        elif defect == 'shifted_time':
            rows[250]['time_s'] += 0.05
        elif defect == 'missing_check':
            check_rows = []
        elif defect == 'stale_check':
            check_rows[0]['native_frame'] += 1
        else:
            for row in rows:
                row['target_direction_indicator_observed_on'] = False
        try:
            observed = measure(rows, 'synthetic_native_sample', check_rows)
            if defect == 'requested_not_observed' and observed['signal_precedes_departure'] is False:
                rejected.append({'defect': defect, 'error': 'Observed signal absent despite request'})
                continue
        except ValueError as e:
            rejected.append({'defect': defect, 'error': str(e)})
        else:
            raise AssertionError(defect + ' was accepted')
    proof = {
        'format': 'worker-source-trace-diagnostic-v1',
        'assignment_id': PACKAGE.name,
        'assignment_sha256': sha(ASSIGNMENT),
        'measure_code_sha256': sha(HERE / 'measure_lane_change.py'),
        'source_kind': 'synthetic_native_sample',
        'selected_case_proof': False,
        'physical_completion_claimed': False,
        'observations': observations,
        'rejected_inputs': rejected,
        'statutory_boundary': 'Signal order and measured target-lane gap do not establish actual driver ascertainment or legal safety.',
    }
    path = HERE / 'lane-change-diagnostic-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'proof': str(path.relative_to(PACKAGE)), 'sha256': sha(path),
                      'departure_frame': observations['early_signal']['first_body_departure_frame'],
                      'negative_count': len(rejected)}, indent=2))


if __name__ == '__main__':
    main()
