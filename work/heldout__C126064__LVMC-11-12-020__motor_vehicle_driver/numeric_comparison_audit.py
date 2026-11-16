"""Compare original source-backed numeric turn attempts without legal labels."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from marked_course_measurement import measure

ASSIGNMENT = 'heldout__C126064__LVMC-11-12-020__motor_vehicle_driver'
CASES = [ASSIGNMENT + f'__c126064_course_blend-{rank:04d}' for rank in (0, 1, 2)]
SETPOINTS = [0.0, 1.0, 0.5]
FIXED_SCENE = ('municipal_jurisdiction_source', 'intersection_source',
               'authorization_source', 'median_opening_with_intersecting_road',
               'intersection_polygon_xy_m', 'indicated_course_xy_m',
               'physical_markers_xy_m', 'indication_form', 'authority_source_sha256')
CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def audit(directories, *, expected_frames=160, negative_marker=False):
    require(len(directories) == 3, 'Numeric sweep needs all three exact attempts')
    roots = [Path(path) for path in directories]
    authority = [(root / 'authority_source_original.json').read_bytes()
                 for root in roots]
    require(authority[0] == authority[1] == authority[2],
            'Numeric comparison changed original authority source')
    scenes = [json.loads((root / 'marked_intersection.json').read_text())
              for root in roots]
    if negative_marker:
        scenes[1]['physical_markers_xy_m'] = [[999, 999]]
    for rank, (root, scene, case, setpoint) in enumerate(zip(roots, scenes, CASES, SETPOINTS)):
        require(scene.get('case_id') == case, 'Numeric comparison changed exact case identity')
        config = json.loads((root / 'config.json').read_text())
        require(config.get('selected_case_id') == case
                and config.get('case', {}).get('case_id') == case
                and config.get('engineering', {}).get('course_blend') == setpoint,
                'Numeric comparison changed frozen controller setpoint')
        if rank:
            for key in FIXED_SCENE:
                require(scene.get(key) == scenes[0].get(key),
                        'Numeric comparison changed fixed site or marker: ' + key)
        for camera in CAMERAS:
            video = root / camera
            require(video.is_file() and video.stat().st_size > 0,
                    'Numeric comparison lacks original camera: ' + camera)
    measured = [measure(root, case) for root, case in zip(roots, CASES)]
    frames = [item['frame_count'] for item in measured]
    require(len(set(frames)) == 1 and frames[0] == expected_frames,
            'Numeric comparison changed original capture duration')
    maps = [(root / 'video_frames.jsonl').read_bytes() for root in roots]
    require(maps[0] == maps[1] == maps[2],
            'Numeric comparison changed original frame map')
    bodies = [rows(root / 'turn_body.jsonl') for root in roots]
    require(all(body[0]['corners_xy_m'] == bodies[0][0]['corners_xy_m']
                and body[-1]['corners_xy_m'] == bodies[0][-1]['corners_xy_m']
                for body in bodies[1:]), 'Numeric comparison changed approach or exit body')
    interiors = [json.dumps(body[1:-1], sort_keys=True) for body in bodies]
    require(len(set(interiors)) == 3,
            'Numeric comparison lacks distinct original interior body paths')
    values = [item['realized_course_deviation']['value_m'] for item in measured]
    require(len(set(values)) == 3,
            'Numeric comparison lacks distinct realized course measurements')
    return {'format': 'worker-numeric-course-comparison-audit',
            'comparison_id': 'marker_numeric_course_offset', 'case_ids': CASES,
            'source_sha256': sha256(authority[0]).hexdigest(),
            'frame_count': frames[0], 'controller_setpoints': SETPOINTS,
            'realized_max_centroid_offset_m': values,
            'fixed_source_and_endpoints_checked': True,
            'physical_acceptance': False, 'legal_conformance': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', action='append', required=True)
    parser.add_argument('--expected-frames', type=int, default=160)
    parser.add_argument('--negative-marker', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, expected_frames=args.expected_frames,
                           negative_marker=args.negative_marker), indent=2))
