"""Independent selected-source branch and one-variable comparison audit."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_lane_change import measure, read_trace

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
PAIRS = {
    'signal_order': ('signal_before_safe', 'signal_after_safe', 'signal_start_frame'),
    'target_lane_gap': ('signal_before_safe', 'signal_before_unsafe', 'target_vehicle_behind_m'),
    'independent_check': ('signal_before_safe', 'signal_before_no_check', 'check_action'),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def selected(suffix, missing_check=False):
    path = HERE / 'selected' / suffix / 'construction.json'
    construction = json.loads(path.read_text())
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    source = PACKAGE / 'selected-source' / suffix
    motion = source / 'native-ego-frames.jsonl'
    checks = source / 'native-driver-checks.jsonl'
    rows = read_trace(motion)
    check_rows = [] if missing_check else read_trace(checks)
    observed = measure(rows, 'synthetic_native_sample', check_rows)
    return config, observed, {'construction': sha(path), 'motion': sha(motion),
                               'check': sha(checks)}


def audit(comparison_id, negative=False):
    require(comparison_id.startswith(PACKAGE.name + '__'), 'Wrong exact assignment')
    suffix = comparison_id[len(PACKAGE.name) + 2:]
    require(suffix in PAIRS, 'Unknown selected comparison')
    baseline_name, contrast_name, variable = PAIRS[suffix]
    plan = json.loads((PACKAGE / 'case-plan.json').read_text())
    pair = next((p for p in plan['comparisons'] if p['comparison_id'] == comparison_id), None)
    require(pair is not None and pair['case_ids'] == [PACKAGE.name + '__' + baseline_name,
                                                       PACKAGE.name + '__' + contrast_name],
            'Comparison case identities differ')
    base_config, base, base_hashes = selected(baseline_name)
    contrast_config, contrast, contrast_hashes = selected(contrast_name, negative)
    excluded = {'case_id', 'selected_case_id', variable}
    require({k: v for k, v in base_config.items() if k not in excluded} ==
            {k: v for k, v in contrast_config.items() if k not in excluded},
            'Comparison changes an undeclared controller or world setting')
    require(base_config[variable] != contrast_config[variable],
            'Comparison did not change declared source variable')
    require(base['same_direction_marked_lane_count'] ==
            contrast['same_direction_marked_lane_count'] == 2 and
            base['first_body_departure_frame'] == contrast['first_body_departure_frame'],
            'Comparison changed frozen multilane departure context')
    if suffix == 'signal_order':
        require(base['signal_precedes_departure'] is True and
                contrast['signal_precedes_departure'] is False and
                base['gap_at_departure_m'] == contrast['gap_at_departure_m'] and
                base['controller_check_action'] == contrast['controller_check_action'],
                'Signal-order source contrast failed')
    elif suffix == 'target_lane_gap':
        require(base['gap_at_departure_m'] > contrast['gap_at_departure_m'] and
                base['controller_decision_to_depart'] is True and
                contrast['controller_decision_to_depart'] is False and
                base['signal_start_frame'] == contrast['signal_start_frame'],
                'Front/rear target-lane gap source contrast failed')
    else:
        require(base['controller_check_action'] == 'evaluated' and
                contrast['controller_check_action'] == 'skipped' and
                base['gap_at_departure_m'] == contrast['gap_at_departure_m'] and
                base['signal_start_frame'] == contrast['signal_start_frame'],
                'Independent-check source contrast failed')
    return {'comparison_id': comparison_id, 'selected_case_ids': pair['case_ids'],
            'changed_variable': variable, 'same_cell_and_departure': True,
            'base_sources': base_hashes, 'contrast_sources': contrast_hashes,
            'synthetic_diagnostic_only': True,
            'legal_threshold_or_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.negative), allow_nan=False))


if __name__ == '__main__':
    main()
