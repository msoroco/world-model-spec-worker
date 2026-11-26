"""Independent raw-source audit of the side-only pedestrian comparison."""

import argparse
import json
from pathlib import Path

FRAMES = 600


def require_file(folder, name):
    path = Path(folder) / name
    if not path.is_file():
        raise ValueError('Missing comparison source: ' + name)
    return path


def lines(path):
    return [json.loads(row) for row in path.read_text().splitlines() if row.strip()]


def audit(a, b):
    cases = []
    for folder, condition in ((Path(a), 'a'), (Path(b), 'b')):
        config = json.loads(require_file(folder, 'config.json').read_text())
        road = json.loads(require_file(folder, 'reviewed-road-source.json').read_text())
        walk = lines(require_file(folder, 'walking-source.jsonl'))
        frames = lines(require_file(folder, 'video_frames.jsonl'))
        if config.get('condition') != condition or len(walk) != FRAMES or len(frames) != FRAMES:
            raise ValueError('Comparison case identity or frame window differs')
        if road.get('sidewalk_present') is not False or road.get('subsection_6_obstruction') is not False:
            raise ValueError('Comparison activation context differs')
        if road.get('traffic_direction_xy') != [1, 0] or road.get('highway_centerline_anchor_xy_m') != [0, 0]:
            raise ValueError('Comparison road orientation differs')
        if any(row.get('pedestrian_heading_xy') != [-1, 0] for row in walk):
            raise ValueError('Comparison pedestrian heading differs')
        if any(row.get('video_frame') != index or row.get('native_frame') != frame.get('native_frame') or
               row.get('time_s') != frame.get('time_s') for index, (row, frame) in enumerate(zip(walk, frames))):
            raise ValueError('Comparison original frame joins differ')
        cases.append({'condition': condition, 'config': config, 'road': road, 'walk': walk, 'frames': frames})
    left, right = cases
    for key in ('law_id', 'cell_id', 'actor', 'duration_s', 'rate_hz', 'frames',
                'required_atoms', 'cameras', 'recording_description'):
        if left['config'][key] != right['config'][key]:
            raise ValueError('Comparison fixed construction differs: ' + key)
    if left['road'] != right['road']:
        raise ValueError('Comparison road source differs')
    for index, (first, second) in enumerate(zip(left['walk'], right['walk'])):
        for key in ('pedestrian_id', 'vehicle_id', 'vehicle_xy_m', 'pedestrian_heading_xy'):
            if first.get(key) != second.get(key):
                raise ValueError('Comparison fixed participant source differs: ' + key)
        if first['pedestrian_xy_m'][0] != second['pedestrian_xy_m'][0]:
            raise ValueError('Comparison longitudinal pedestrian path differs')
        y_a, y_b = first['pedestrian_xy_m'][1], second['pedestrian_xy_m'][1]
        if not (0 < y_a <= left['road']['highway_half_width_m'] and
                -left['road']['highway_half_width_m'] <= y_b < 0):
            raise ValueError('Comparison highway side is not the declared difference at frame ' + str(index))
    return {'format': 'worker-independent-side-comparison', 'passed': True,
            'case_ids': [case['config']['case_id'] for case in cases],
            'frames_per_case': FRAMES, 'fixed_heading_xy': [-1, 0],
            'deliberate_difference': 'pedestrian_highway_side',
            'physical_completion': False, 'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--a', required=True)
    parser.add_argument('--b', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.a, args.b)))
