"""Independent saved-source audit of the two ordinary-vehicle lane probes."""

import argparse
import hashlib
import json
from pathlib import Path


ASSIGNMENT = 'training__C179776__NRS-484B-587-2a__motor_vehicle_driver'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def compare(inside, outside):
    inside, outside = Path(inside), Path(outside)
    fixed_sources = ('designation-source.json', 'road.xodr', 'native-road-readback.json')
    for name in fixed_sources:
        if digest(inside / name) != digest(outside / name):
            raise ValueError('Controlled fixed source differs: ' + name)
    actor_pairs = [rows(path / 'native-raw-actors.jsonl') for path in (inside, outside)]
    control_pairs = [rows(path / 'control-intent.jsonl') for path in (inside, outside)]
    frame_pairs = [rows(path / 'video_frames.jsonl') for path in (inside, outside)]
    if any(len(part) != 600 for pair in (actor_pairs, control_pairs, frame_pairs) for part in pair):
        raise ValueError('Full paired original source absent')
    expected = [ASSIGNMENT + '__probe_a', ASSIGNMENT + '__probe_b']
    difference_frames = 0
    for i in range(600):
        first, second = (pair[i] for pair in actor_pairs)
        if [first.get('case_id'), second.get('case_id')] != expected:
            raise ValueError('Exact paired case identity differs')
        first_body, second_body = first['actors'][0], second['actors'][0]
        if any(first_body.get(key) != second_body.get(key) for key in
               ('blueprint_id', 'bbox_half_length_m', 'bbox_half_width_m', 'x_m', 'speed_mps')):
            raise ValueError('Controlled actor or longitudinal motion differs')
        a, b = (pair[i] for pair in control_pairs)
        target_a, target_b = a.get('target_xy_m'), b.get('target_xy_m')
        if (not isinstance(target_a, list) or not isinstance(target_b, list) or
                len(target_a) != 2 or len(target_b) != 2 or target_a[0] != target_b[0]):
            raise ValueError('Controlled longitudinal target differs')
        fa, fb = (pair[i] for pair in frame_pairs)
        if (fa.get('video_frame') != fb.get('video_frame') or
                fa.get('time_s') != fb.get('time_s') or
                set(fa.get('camera_native_frames', {})) !=
                set(fb.get('camera_native_frames', {}))):
            raise ValueError('Controlled camera/time policy differs')
        difference_frames += abs(first_body['y_m'] - second_body['y_m']) > 1
    if difference_frames < 250:
        raise ValueError('Declared lateral difference not observed')
    return {'format': 'c179776-independent-lane-comparison-v1',
            'passed': True, 'case_ids': expected,
            'fixed_source_sha256': {name: digest(inside / name) for name in fixed_sources},
            'observed_lateral_difference_frames': difference_frames,
            'full_frame_count': 600, 'legal_verdict': None,
            'physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--inside', required=True)
    parser.add_argument('--outside', required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.inside, args.outside), sort_keys=True))
