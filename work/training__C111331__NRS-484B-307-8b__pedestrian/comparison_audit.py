"""Independent source comparison of fixed setup and declared variations."""

import argparse
import json
from pathlib import Path

from finalize import measure

HERE = Path(__file__).resolve().parent


def audit(comparison_id, left_path, right_path):
    plan = json.loads((HERE / 'case-plan.json').read_text())
    comparison = next((item for item in plan['comparisons']
                       if item['comparison_id'] == comparison_id), None)
    if comparison is None:
        raise ValueError('Unknown exact comparison')
    left, right = measure(left_path), measure(right_path)
    a, b = left['config'], right['config']
    if [a['case_id'], b['case_id']] != comparison['case_ids']:
        raise ValueError('Comparison case order or identity differs')
    fixed = ('cell_id', 'law_id', 'actor', 'map_sha256', 'traffic_head_id',
             'other_device_id', 'requested_traffic', 'frames', 'rate_hz',
             'duration_s', 'cameras', 'roadway_y_abs_max_m')
    if any(a[key] != b[key] for key in fixed):
        raise ValueError('Fixed comparison condition differs')
    if left['join']['frames'] != 600 or right['join']['frames'] != 600:
        raise ValueError('Incomplete comparison source window')
    differences = comparison['deliberate_differences']
    if differences == ['requested_pedestrian_highway_entry']:
        if a['requested_other_device'] != b['requested_other_device'] or a['requested_entry'] == b['requested_entry']:
            raise ValueError('Entry comparison variable differs from plan')
        observed = [left['join']['first_roadway_footprint_frame'] is not None,
                    right['join']['first_roadway_footprint_frame'] is not None]
        if observed != [a['requested_entry'], b['requested_entry']]:
            raise ValueError('Measured footprint entry contrast absent')
    else:
        if not a['requested_entry'] or not b['requested_entry'] or a['requested_other_device'] == b['requested_other_device']:
            raise ValueError('Other-device comparison variable differs from plan')
        if any(value['join']['first_roadway_footprint_frame'] is None for value in (left, right)):
            raise ValueError('Fixed highway-entry source absent')
    return {'format': 'c111331-independent-comparison-v1',
            'comparison_id': comparison_id, 'case_ids': comparison['case_ids'],
            'fixed_conditions_checked': list(fixed),
            'deliberate_differences_checked': differences,
            'source_hashes': {'left': left['source_hashes'], 'right': right['source_hashes']},
            'software_source_comparison_passed': True,
            'original_native_verified': bool(left['original_native_source'] and
                                              right['original_native_source']),
            'device_governance_verified': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', required=True)
    parser.add_argument('--right', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.comparison, args.left, args.right)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'comparison_id': args.comparison, 'passed': True}))
