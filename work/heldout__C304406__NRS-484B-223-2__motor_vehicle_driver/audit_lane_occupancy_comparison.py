"""Independent right-versus-center saved-source comparison, without a legal verdict."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from three_lane_finalizer import PREFIX


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def source_case(attempt, processing, suffix):
    attempt, processing = Path(attempt), Path(processing)
    receipt = json.loads(processing.read_text())
    case_id = PREFIX + suffix
    if (receipt.get('case_id') != case_id or receipt.get('passed') is not True or
            receipt.get('recorded_only') is not True or
            receipt.get('originals_preserved') is not True or
            receipt.get('missing_evidence') is not False):
        raise ValueError('Saved lane case status or identity differs')
    report = json.loads((processing.parent / 'analysis/analysis-report.json').read_text())
    result = json.loads((processing.parent / 'analysis/result.json').read_text())
    if report.get('case_id') != case_id or result.get('case_id') != case_id:
        raise ValueError('Saved lane report/result case differs')
    observation = report['measurements']['three_lane_observation']
    if (observation.get('method') != 'measure_three_lane_sources' or
            result.get('measured_values', {}).get('three_lane_observation') != observation['value']):
        raise ValueError('Saved lane measured result differs')
    for name, checksum in observation['sources'].items():
        path = attempt / name
        if not path.is_file() or digest(path) != checksum:
            raise ValueError('Saved lane original source differs: ' + name)
    return {'attempt': attempt, 'processing': processing,
            'receipt': receipt, 'report': report, 'result': result,
            'observation': observation['value']}


def audit(right_attempt, right_processing, center_attempt, center_processing):
    right = source_case(right_attempt, right_processing, 'right_baseline')
    center = source_case(center_attempt, center_processing, 'center_default')
    for name in ('three_lane_context.json', 'three_lane_map_readback.json',
                 'video_frames.jsonl'):
        if digest(right['attempt'] / name) != digest(center['attempt'] / name):
            raise ValueError('Fixed three-lane context or frame map changed: ' + name)
    right_config = json.loads((right['attempt'] / 'config.json').read_text())
    center_config = json.loads((center['attempt'] / 'config.json').read_text())
    for key in ('law_id', 'cell_id', 'actor', 'rate_hz', 'frames', 'duration_s',
                'travel_direction', 'cameras', 'required_atoms', 'source_packets'):
        if right_config.get(key) != center_config.get(key):
            raise ValueError('Fixed three-lane configuration changed: ' + key)
    a = rows(right['attempt'] / 'three_lane_frames.jsonl')
    b = rows(center['attempt'] / 'three_lane_frames.jsonl')
    if not a or len(a) != len(b):
        raise ValueError('Lane source frame count changed')
    for first, second in zip(a, b):
        for key in ('frame', 'time_s', 'road_id', 'road_travel_tangent_xy',
                    'ego_actor_id', 'lane_polygons_xy'):
            if first.get(key) != second.get(key):
                raise ValueError('Fixed lane source changed: ' + key)
        if any(x[0] != y[0] for x, y in zip(first['ego_corners_xy'], second['ego_corners_xy'])):
            raise ValueError('Subject longitudinal body path changed')
    trace_a = rows(right['attempt'] / 'trace.jsonl')
    trace_b = rows(center['attempt'] / 'trace.jsonl')
    if len(trace_a) != len(trace_b) or any(
            (a['frame'], a['time_s'], a['position_m'][0]) !=
            (b['frame'], b['time_s'], b['position_m'][0])
            for a, b in zip(trace_a, trace_b)):
        raise ValueError('Fixed original trace frame or longitudinal path changed')
    overlap_a = [row['body_lane_overlap_fraction'] for row in right['observation']['observations']]
    overlap_b = [row['body_lane_overlap_fraction'] for row in center['observation']['observations']]
    if (not all(row['right'] > 0.95 and row['center'] < 0.05 for row in overlap_a) or
            not all(row['center'] > 0.95 and row['right'] < 0.05 for row in overlap_b)):
        raise ValueError('Deliberate right-to-center occupancy contrast missing')
    return {'format': 'worker-three-lane-occupancy-comparison-audit',
            'comparison_id': 'center_default',
            'right_case': PREFIX + 'right_baseline',
            'center_case': PREFIX + 'center_default',
            'right_processing_sha256': digest(right['processing']),
            'center_processing_sha256': digest(center['processing']),
            'fixed_map_sha256': digest(right['attempt'] / 'three_lane_map_readback.json'),
            'frames': len(a), 'right_overlap_min': min(row['right'] for row in overlap_a),
            'center_overlap_min': min(row['center'] for row in overlap_b),
            'fixed_conditions_passed': True, 'deliberate_difference_passed': True,
            'physical_or_legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--right-attempt', required=True)
    parser.add_argument('--right-processing', required=True)
    parser.add_argument('--center-attempt', required=True)
    parser.add_argument('--center-processing', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.right_attempt, args.right_processing,
                   args.center_attempt, args.center_processing)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
