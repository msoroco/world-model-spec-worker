"""Independent saved-source comparison for the two municipal street probes."""
import argparse
import json
from pathlib import Path


ASSIGNMENT = 'training__C150129__LVMC-11-52-340__motor_vehicle_driver'


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit(left, right):
    left, right = Path(left), Path(right)
    config_a, config_b = read(left / 'config.json'), read(right / 'config.json')
    expected = [ASSIGNMENT + '__controlled_1', ASSIGNMENT + '__controlled_2']
    if [config_a['case_id'], config_b['case_id']] != expected:
        raise ValueError('Exact controlled case pair required')
    if [config_a['parking_case'], config_b['parking_case']] != ['outside_city_space', 'inside_city_space']:
        raise ValueError('Requested parking comparison differs')
    fixed_config = ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s',
                    'required_atoms', 'source_packets', 'cameras', 'recording_description')
    for key in fixed_config:
        if config_a[key] != config_b[key]:
            raise ValueError('Fixed configuration changed: ' + key)
    inv_a, inv_b = read(left / 'parking-inventory.json'), read(right / 'parking-inventory.json')
    if inv_a != inv_b:
        raise ValueError('Posted space or Native marker changed')
    rev_a, rev_b = read(left / 'review.json'), read(right / 'review.json')
    for key in ('city_street', 'council_designation', 'posting_or_marking',
                'subject_vehicle_status'):
        if rev_a[key] != rev_b[key]:
            raise ValueError('Independent source assertion changed: ' + key)
    pose_a, pose_b = rows(left / 'vehicle-poses.jsonl'), rows(right / 'vehicle-poses.jsonl')
    if len(pose_a) != 600 or len(pose_b) != 600:
        raise ValueError('Complete 600-frame pair required')
    for a, b in zip(pose_a, pose_b):
        for key in ('video_frame', 'native_frame', 'time_s', 'vehicle_id',
                    'speed_mps', 'blueprint_id', 'yaw_rad', 'bbox_half_length_m',
                    'bbox_half_width_m'):
            if a[key] != b[key]:
                raise ValueError('Fixed subject sample changed: ' + key)
    metric_a = read(left / 'analysis-report.json')['measurements']['municipal_street_parking']['value']
    metric_b = read(right / 'analysis-report.json')['measurements']['municipal_street_parking']['value']
    fixed_metric = ('space_id', 'stationary_proxy_frames', 'city_street_source_id',
                    'council_designation_source_id', 'posting_or_marking_source_id',
                    'subject_status_source_id', 'legal_result')
    for key in fixed_metric:
        if metric_a[key] != metric_b[key]:
            raise ValueError('Fixed measurement changed: ' + key)
    if metric_a['occupied_and_stationary_proxy_frames']:
        raise ValueError('Outside probe occupied posted space')
    if not metric_b['occupied_and_stationary_proxy_frames']:
        raise ValueError('Inside probe did not occupy posted space')
    return {'format': 'c150129-independent-comparison-audit',
            'case_ids': expected, 'passed': True,
            'fixed_sample_count': len(pose_a),
            'outside_occupied_stationary_frames': len(metric_a['occupied_and_stationary_proxy_frames']),
            'inside_occupied_stationary_frames': len(metric_b['occupied_and_stationary_proxy_frames']),
            'physical_or_legal_acceptance': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--left', required=True)
    parser.add_argument('--right', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.left, args.right)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
