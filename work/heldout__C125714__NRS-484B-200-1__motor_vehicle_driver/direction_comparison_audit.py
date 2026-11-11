"""Independent source audit for the east/west right-half comparison.

This checks saved original geometry and join identity. It makes no legal or
physical acceptance claim; video visibility still needs a separate review.
"""

import argparse
from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path


ASSIGNMENT = 'heldout__C125714__NRS-484B-200-1__motor_vehicle_driver'
SOURCES = ('video_frames.jsonl', 'trace.jsonl',
           'directed_roadway_footprints.jsonl')


def _source(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing original comparison source: ' + name)
    raw = path.read_bytes()
    if not raw:
        raise ValueError('Empty original comparison source: ' + name)
    return [json.loads(line) for line in raw.splitlines()], sha256(raw).hexdigest()


def _case(root, suffix, direction):
    config_path = root / 'config.json'
    if not config_path.is_file():
        raise ValueError('Missing exact comparison config')
    config = json.loads(config_path.read_text())
    case_id = f'{ASSIGNMENT}__baseline_right_{suffix}'
    if (config.get('selected_case_id'), config.get('law_id'), config.get('cell_id'),
            config.get('actor')) != (case_id, 'NRS-484B-200-1', 'C125714',
                                    'motor_vehicle_driver'):
        raise ValueError('Direction comparison exact case identity differs')
    if config.get('travel_direction') != suffix:
        raise ValueError('Direction comparison config direction differs')
    sources = {name: _source(root, name) for name in SOURCES}
    frames, trace, geometry = (sources[name][0] for name in SOURCES)
    if not frames or not (len(frames) == len(trace) == len(geometry)):
        raise ValueError('Direction comparison original frame counts differ')
    widths = []
    identities = set()
    for index, (video, motion, road) in enumerate(zip(frames, trace, geometry)):
        frame, time_s = video.get('carla_frame'), video.get('time_s')
        if (video.get('video_frame') != index or motion.get('frame') != frame or
                road.get('frame') != frame or motion.get('time_s') != time_s or
                road.get('time_s') != time_s):
            raise ValueError('Direction comparison original frame join differs')
        if index and (frame != frames[index-1]['carla_frame'] + 1 or
                      abs(time_s - frames[index-1]['time_s'] - .05) > 1e-4):
            raise ValueError('Direction comparison sources are not continuous 20 Hz')
        identities.add(road.get('ego_id'))
        tx, ty = road['travel_tangent_xy']
        if not all(isfinite(v) for v in (tx, ty)) or tx * direction < .8:
            raise ValueError('Direction comparison observed route direction differs')
        norm = hypot(tx, ty)
        right = (-ty/norm, tx/norm)
        centre = road['roadway_center_point_xy']
        def offset(point):
            return sum((point[i]-centre[i])*right[i] for i in (0, 1))
        left, right_edge = (offset(road[key]) for key in
                            ('left_road_edge_xy', 'right_road_edge_xy'))
        if not left < 0 < right_edge:
            raise ValueError('Direction comparison directed edges are inverted')
        corners = road.get('ego_corners')
        if not isinstance(corners, list) or len(corners) != 4:
            raise ValueError('Direction comparison lacks full body footprint')
        if min(offset(corner) for corner in corners) < 0:
            raise ValueError('Direction comparison body leaves right half')
        widths.append(right_edge - left)
    if len(identities) != 1 or not next(iter(identities)):
        raise ValueError('Direction comparison subject identity differs within case')
    return {'case_id': case_id, 'frame_count': len(frames),
            'minimum_road_width_m': min(widths),
            'source_sha256': {name: sources[name][1] for name in SOURCES},
            'config_sha256': sha256(config_path.read_bytes()).hexdigest(),
            'fixed': {key: config.get(key) for key in
                      ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s',
                       'cameras', 'required_atoms', 'source_packets')}}


def audit(east_attempt, west_attempt):
    east = _case(Path(east_attempt), 'east', 1)
    west = _case(Path(west_attempt), 'west', -1)
    if east['fixed'] != west['fixed']:
        raise ValueError('Direction comparison fixed construction conditions differ')
    if east['frame_count'] != west['frame_count']:
        raise ValueError('Direction comparison capture durations differ')
    return {'format': 'worker-right-half-direction-comparison-audit',
            'comparison_id': 'direction',
            'case_ids': [east['case_id'], west['case_id']],
            'source_bindings': [east, west],
            'observed_directions': ['east', 'west'],
            'both_bodies_entirely_right': True,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--east-attempt', required=True)
    parser.add_argument('--west-attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior comparison audit')
    output.write_text(json.dumps(audit(args.east_attempt, args.west_attempt),
                                 indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
