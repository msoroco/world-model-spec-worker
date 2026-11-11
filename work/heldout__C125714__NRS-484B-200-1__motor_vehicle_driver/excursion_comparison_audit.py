"""Independent original-source comparison of right-half baseline and excursion.

This checks realized body crossing in retained source rows. It does not decide
whether any statutory exception applies or whether a diagnostic is physical.
"""

import argparse
from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path


ASSIGNMENT = 'heldout__C125714__NRS-484B-200-1__motor_vehicle_driver'
SOURCES = ('video_frames.jsonl', 'trace.jsonl',
           'directed_roadway_footprints.jsonl')
FIXED = ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s', 'cameras',
         'required_atoms', 'source_packets', 'travel_direction')


def _load(root, name):
    path = root / name
    if not path.is_file() or not path.stat().st_size:
        raise ValueError('Missing original excursion source: ' + name)
    raw = path.read_bytes()
    return [json.loads(line) for line in raw.splitlines()], sha256(raw).hexdigest()


def _case(root, suffix):
    config_path = root / 'config.json'
    if not config_path.is_file():
        raise ValueError('Missing exact excursion config')
    config = json.loads(config_path.read_text())
    case_id = ASSIGNMENT + '__' + suffix
    if (config.get('selected_case_id'), config.get('law_id'), config.get('cell_id'),
            config.get('actor'), config.get('travel_direction')) != (
            case_id, 'NRS-484B-200-1', 'C125714', 'motor_vehicle_driver', 'east'):
        raise ValueError('Excursion exact identity or direction differs')
    sources = {name: _load(root, name) for name in SOURCES}
    frames, trace, roadway = (sources[name][0] for name in SOURCES)
    if not frames or not (len(frames) == len(trace) == len(roadway)):
        raise ValueError('Excursion original frame counts differ')
    min_offsets = []
    road_ids = set()
    lane_ids = set()
    ego_ids = set()
    widths = []
    for index, (mapping, motion, road) in enumerate(zip(frames, trace, roadway)):
        frame, time_s = mapping.get('carla_frame'), mapping.get('time_s')
        if (mapping.get('video_frame') != index or motion.get('frame') != frame or
                road.get('frame') != frame or motion.get('time_s') != time_s or
                road.get('time_s') != time_s):
            raise ValueError('Excursion original frame/time join differs')
        tx, ty = road['travel_tangent_xy']
        norm = hypot(tx, ty)
        if not all(isfinite(v) for v in (tx, ty)) or norm < .8 or tx/norm < .8:
            raise ValueError('Excursion original travel direction differs')
        right = (-ty/norm, tx/norm)
        centre = road['roadway_center_point_xy']
        def offset(point):
            return sum((point[i]-centre[i])*right[i] for i in (0, 1))
        if not offset(road['left_road_edge_xy']) < 0 < offset(road['right_road_edge_xy']):
            raise ValueError('Excursion original directed road edges differ')
        corners = road.get('ego_corners')
        if not isinstance(corners, list) or len(corners) != 4:
            raise ValueError('Excursion original full body footprint missing')
        min_offsets.append(min(offset(corner) for corner in corners))
        road_ids.add(road.get('subject_road_id'))
        lane_ids.add(road.get('subject_lane_id'))
        ego_ids.add(road.get('ego_id'))
        widths.append(offset(road['right_road_edge_xy']) -
                      offset(road['left_road_edge_xy']))
    if len(road_ids) != 1 or len(lane_ids) != 1 or None in road_ids | lane_ids:
        raise ValueError('Excursion original route identity changes')
    if len(ego_ids) != 1 or None in ego_ids:
        raise ValueError('Excursion original subject identity changes')
    return {'case_id': case_id, 'frame_count': len(frames),
            'minimum_body_right_offset_m': min(min_offsets),
            'first_crossing_frame': next((frames[i]['carla_frame'] for i, v in
                                          enumerate(min_offsets) if v < 0), None),
            'road_id': next(iter(road_ids)), 'lane_id': next(iter(lane_ids)),
            'ego_id': next(iter(ego_ids)),
            'minimum_road_width_m': min(widths),
            'source_sha256': {name: sources[name][1] for name in SOURCES},
            'config_sha256': sha256(config_path.read_bytes()).hexdigest(),
            'fixed': {key: config.get(key) for key in FIXED}}


def audit(baseline_attempt, excursion_attempt):
    baseline = _case(Path(baseline_attempt), 'baseline_right_east')
    excursion = _case(Path(excursion_attempt), 'unexcepted_left')
    if baseline['fixed'] != excursion['fixed']:
        raise ValueError('Excursion fixed construction conditions differ')
    if (baseline['frame_count'], baseline['road_id'], baseline['lane_id']) != (
            excursion['frame_count'], excursion['road_id'], excursion['lane_id']):
        raise ValueError('Excursion fixed route/frame conditions differ')
    if abs(baseline['minimum_road_width_m'] - excursion['minimum_road_width_m']) > .01:
        raise ValueError('Excursion fixed roadway width differs')
    if baseline['minimum_body_right_offset_m'] < 0:
        raise ValueError('Excursion baseline already crosses left half')
    if excursion['first_crossing_frame'] is None:
        raise ValueError('Excursion original full body never crosses centerline')
    return {'format': 'worker-right-half-excursion-comparison-audit',
            'comparison_id': 'excursion',
            'case_ids': [baseline['case_id'], excursion['case_id']],
            'source_bindings': [baseline, excursion],
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline-attempt', required=True)
    parser.add_argument('--excursion-attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain previous excursion audit receipt')
    output.write_text(json.dumps(audit(args.baseline_attempt, args.excursion_attempt),
                                 indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
