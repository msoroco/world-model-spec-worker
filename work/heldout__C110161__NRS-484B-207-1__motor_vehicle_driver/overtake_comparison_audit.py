"""Independent source-bound audit of the two planned overtake comparisons.

This checks construction isolation and measured differences, never legal safety.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from overtake_measurement import measure


PREFIX = 'heldout__C110161__NRS-484B-207-1__motor_vehicle_driver__'
PAIRS = {
    'left_pass_clearance': ('left_pass_wide', 'left_pass_narrow',
                            'target_left_gap_m', 'min_abreast_lateral_gap_m'),
    'return_clearance_order': ('return_before_clear', 'return_after_clear',
                               'requested_return_clearance_m',
                               'clearance_at_first_return_m'),
}
FIXED = ('law_id', 'cell_id', 'actor', 'rate_hz', 'frames', 'duration_s',
         'cameras', 'required_atoms', 'source_packets')
ORIGINAL_FIXED = ('road_tangent_xy', 'other_id', 'other_heading_xy',
                  'other_corners')


def _read_attempt(root, expected_case):
    root = Path(root)
    config_path = root / 'config.json'
    source_path = root / 'participant_footprints.jsonl'
    if not config_path.is_file() or not source_path.is_file():
        raise ValueError('Missing original comparison configuration or footprint source')
    config = json.loads(config_path.read_text())
    if config.get('selected_case_id') != PREFIX + expected_case:
        raise ValueError('Comparison case identity differs')
    for key in FIXED + ('target_left_gap_m', 'requested_return_clearance_m'):
        if key not in config:
            raise ValueError('Missing comparison construction field: ' + key)
    if (config['law_id'], config['cell_id'], config['actor']) != (
            'NRS-484B-207-1', 'C110161', 'motor_vehicle_driver'):
        raise ValueError('Comparison law/cell/actor differs')
    observed = measure(source_path)
    rows = [json.loads(line) for line in source_path.read_text().splitlines()]
    return config, observed, {
        'config.json': sha256(config_path.read_bytes()).hexdigest(),
        'participant_footprints.jsonl': observed['source_sha256'],
    }, rows


def audit(comparison_id, first, second):
    if comparison_id not in PAIRS:
        raise ValueError('Unknown overtake comparison')
    first_case, second_case, changed, measurement = PAIRS[comparison_id]
    left, left_obs, left_sources, left_rows = _read_attempt(first, first_case)
    right, right_obs, right_sources, right_rows = _read_attempt(second, second_case)
    for key in FIXED:
        if left[key] != right[key]:
            raise ValueError('Fixed comparison condition changed: ' + key)
    other_knob = ('requested_return_clearance_m' if changed == 'target_left_gap_m'
                  else 'target_left_gap_m')
    if left[other_knob] != right[other_knob]:
        raise ValueError('Fixed comparison condition changed: ' + other_knob)
    if left[changed] == right[changed]:
        raise ValueError('Declared comparison construction does not differ')
    if len(left_rows) != len(right_rows) or any(
            any(a.get(key) != b.get(key) for key in ORIGINAL_FIXED)
            for a, b in zip(left_rows, right_rows)):
        raise ValueError('Fixed original roadway or overtaken participant changed')
    left_value, right_value = left_obs[measurement], right_obs[measurement]
    if left_value == right_value:
        raise ValueError('Original frame comparison measurement does not differ')
    for observed in (left_obs, right_obs):
        if not observed['all_abreast_left']:
            raise ValueError('Original comparison pass did not stay left')
    return {'format': 'worker-overtake-comparison-audit',
            'comparison_id': comparison_id,
            'case_ids': [PREFIX + first_case, PREFIX + second_case],
            'fixed_fields': list(FIXED) + [other_knob] + list(ORIGINAL_FIXED),
            'deliberate_difference': changed,
            'observed_difference': measurement,
            'construction_values': [left[changed], right[changed]],
            'measured_values': [left_value, right_value],
            'source_sha256': [left_sources, right_sources],
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', choices=sorted(PAIRS), required=True)
    parser.add_argument('--first', required=True)
    parser.add_argument('--second', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior comparison audit')
    result = audit(args.comparison, args.first, args.second)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
