"""Independent same-side parking-position comparison over saved source streams."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def compare(far, near):
    far, near = Path(far), Path(near)
    for name in ('road.xodr', 'video_frames.jsonl'):
        if sha(far/name) != sha(near/name):
            raise ValueError('Fixed road or frame timing differs: ' + name)
    a_context = json.loads((far/'entrance-context.json').read_text())
    b_context = json.loads((near/'entrance-context.json').read_text())
    if a_context != b_context or a_context.get('source_kind') != 'synthetic_diagnostic':
        raise ValueError('Fixed source context differs or fixture source unmarked')
    a, b = rows(far/'native-vehicle.jsonl'), rows(near/'native-vehicle.jsonl')
    if len(a) != 600 or len(b) != 600:
        raise ValueError('Paired original-shaped motion is incomplete')
    for index, (left, right) in enumerate(zip(a, b)):
        for key in ('native_frame', 'video_frame', 'time_s', 'actor_id', 'blueprint_id'):
            if left.get(key) != right.get(key):
                raise ValueError('Fixed actor or timing differs at frame ' + str(index))
    if not all(row['speed_mps'] <= .1 for row in a[-100:] + b[-100:]):
        raise ValueError('A final parked position is missing')
    if not all(row['center_xy_m'][1] < 0 for row in a[-100:] + b[-100:]):
        raise ValueError('A parking position crossed the entrance side')
    entrance = a_context['entrance']
    def gap(row):
        xs = [point[0] for point in row['body_xy_m']]
        return max(0, entrance['x_min_m'] - max(xs), min(xs) - entrance['x_max_m'])
    a_gap, b_gap = min(map(gap, a[-100:])), min(map(gap, b[-100:]))
    if not (a_gap > b_gap and a_gap == 12 and b_gap == 0):
        raise ValueError('Deliberate raw parked-position contrast is absent')
    return {'format': 'c229410-source-comparison-v1', 'passed': True,
            'far_motion_sha256': sha(far/'native-vehicle.jsonl'),
            'near_motion_sha256': sha(near/'native-vehicle.jsonl'),
            'fixed_map_sha256': sha(far/'road.xodr'),
            'fixed_frame_map_sha256': sha(far/'video_frames.jsonl'),
            'far_raw_body_edge_gap_m': a_gap, 'near_raw_body_edge_gap_m': b_gap,
            'statutory_reference_method_adopted': False,
            'physical_or_legal_result_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--far', required=True)
    parser.add_argument('--near', required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.far, args.near), sort_keys=True))
