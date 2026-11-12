"""Independent saved-source comparison for the two marked-turn courses.

This checks source identity and measured course contrast. It makes no municipal
authorization or legal conformance finding and does not consume expected labels.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from marked_course_measurement import measure

ASSIGNMENT = 'heldout__C126064__LVMC-11-12-020__motor_vehicle_driver'
INDICATED = ASSIGNMENT + '__indicated_course'
DIVERGENT = ASSIGNMENT + '__divergent_course'


def _source(path, name):
    source = Path(path) / name
    if not source.is_file():
        raise ValueError('Missing original compared source: ' + name)
    return source.read_bytes()


def audit(indicated, divergent, *, expected_frames=None):
    indicated, divergent = Path(indicated), Path(divergent)
    authority_a = _source(indicated, 'authority_source_original.json')
    authority_b = _source(divergent, 'authority_source_original.json')
    if authority_a != authority_b:
        raise ValueError('Compared turns changed original authority or site source')
    scene_a = json.loads(_source(indicated, 'marked_intersection.json'))
    scene_b = json.loads(_source(divergent, 'marked_intersection.json'))
    if (scene_a.get('case_id'), scene_b.get('case_id')) != (INDICATED, DIVERGENT):
        raise ValueError('Compared exact case identities changed')
    for key in ('municipal_jurisdiction_source', 'intersection_source',
                'authorization_source', 'median_opening_with_intersecting_road',
                'intersection_polygon_xy_m', 'indicated_course_xy_m',
                'physical_markers_xy_m', 'authority_source_sha256'):
        if scene_a.get(key) != scene_b.get(key):
            raise ValueError('Compared turns changed fixed site or marker: ' + key)
    left = measure(indicated, INDICATED)
    right = measure(divergent, DIVERGENT)
    if left['frame_count'] != right['frame_count']:
        raise ValueError('Compared turns changed original capture duration')
    if expected_frames is not None and left['frame_count'] != expected_frames:
        raise ValueError('Compared turn does not have declared frame count')
    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        # The independent delivery audit later performs full video decoding.
        if expected_frames is not None:
            for directory in (indicated, divergent):
                video = directory / (name + '.mkv')
                if not video.is_file() or video.stat().st_size == 0:
                    raise ValueError('Missing original compared camera: ' + name)
    path_a = _source(indicated, 'turn_body.jsonl')
    path_b = _source(divergent, 'turn_body.jsonl')
    if path_a == path_b:
        raise ValueError('Compared turns have identical original body paths')
    distances_a = [row['centroid_to_indicated_course_m'] for row in left['observations']]
    distances_b = [row['centroid_to_indicated_course_m'] for row in right['observations']]
    if distances_a == distances_b:
        raise ValueError('Compared turns lack measured course contrast')
    return {'format': 'worker-marked-turn-comparison-audit',
            'comparison_id': 'marked_turn_course',
            'case_ids': [INDICATED, DIVERGENT],
            'source_sha256': sha256(authority_a).hexdigest(),
            'frame_count': left['frame_count'],
            'measured_centroid_distance_m': [distances_a, distances_b],
            'fixed_site_and_markers_checked': True,
            'legal_conformance': None, 'physical_acceptance': False}


def _fixture(root, case_id, body_y):
    root.mkdir()
    scene = {'case_id': case_id, 'municipal_jurisdiction_source': 'CPU fixture only',
             'intersection_source': 'CPU fixture only',
             'authorization_source': 'CPU fixture only',
             'median_opening_with_intersecting_road': True, 'ego_actor_id': 7,
             'intersection_polygon_xy_m': [[-2, -2], [4, -2], [4, 4], [-2, 4]],
             'physical_markers_xy_m': [[1, 1]],
             'indicated_course_xy_m': [[0, 0], [3, 0], [3, 3]]}
    authority = {key: scene[key] for key in (
        'municipal_jurisdiction_source', 'intersection_source', 'authorization_source',
        'median_opening_with_intersecting_road', 'intersection_polygon_xy_m',
        'indicated_course_xy_m')}
    raw = json.dumps(authority).encode()
    (root / 'authority_source_original.json').write_bytes(raw)
    scene['authority_source_sha256'] = sha256(raw).hexdigest()
    (root / 'marked_intersection.json').write_text(json.dumps(scene))
    bodies = [{'frame': 10 + i, 'time_s': i / 20, 'actor_id': 7,
               'corners_xy_m': [[i, body_y], [i + .4, body_y],
                                [i + .4, body_y + .4], [i, body_y + .4]]}
              for i in range(3)]
    frames = [{'video_frame': i, 'carla_frame': 10 + i, 'time_s': i / 20}
              for i in range(3)]
    for name, rows in (('turn_body.jsonl', bodies), ('video_frames.jsonl', frames)):
        (root / name).write_text(''.join(json.dumps(row) + '\n' for row in rows))


def selftest():
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        a, b = root / 'indicated', root / 'divergent'
        _fixture(a, INDICATED, 0.)
        _fixture(b, DIVERGENT, 1.)
        assert audit(a, b)['frame_count'] == 3
        scene = json.loads((b / 'marked_intersection.json').read_text())
        scene['physical_markers_xy_m'] = [[2, 1]]
        (b / 'marked_intersection.json').write_text(json.dumps(scene))
        try:
            audit(a, b)
        except ValueError as error:
            assert 'fixed site or marker' in str(error)
        else:
            raise AssertionError('changed marker accepted')
        _fixture_repair = json.loads((a / 'marked_intersection.json').read_text())
        _fixture_repair['case_id'] = DIVERGENT
        (b / 'marked_intersection.json').write_text(json.dumps(_fixture_repair))
        (b / 'turn_body.jsonl').write_bytes((a / 'turn_body.jsonl').read_bytes())
        try:
            audit(a, b)
        except ValueError as error:
            assert 'identical original body paths' in str(error)
        else:
            raise AssertionError('unchanged course accepted')
    return {'selftest_passed': True, 'positive': 1, 'negative': 2}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--indicated')
    parser.add_argument('--divergent')
    parser.add_argument('--expected-frames', type=int, default=160)
    parser.add_argument('--selftest', action='store_true')
    args = parser.parse_args()
    if args.selftest:
        print(json.dumps(selftest(), indent=2))
    else:
        if not args.indicated or not args.divergent:
            parser.error('Both original attempt directories are required')
        print(json.dumps(audit(args.indicated, args.divergent,
                               expected_frames=args.expected_frames), indent=2))
