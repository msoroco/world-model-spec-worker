"""Synthetic saved-source positive/negative checks for cycle parking geometry."""
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from measure_parking import AID, CAMERAS, measure


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def expect_reject(root, changed, expected):
    path = root / changed
    old = path.read_bytes()
    try:
        if changed.endswith('.jsonl'):
            lines = path.read_text().splitlines()
            first = json.loads(lines[0])
            if expected == 'frame':
                first['native_frame'] += 100
            elif expected == 'provenance':
                first['source_kind'] = 'original_native_pose'
            elif expected == 'operator':
                first['operator_actor_id'] = 99
            lines[0] = json.dumps(first)
            path.write_text('\n'.join(lines) + '\n')
        else:
            data = json.loads(path.read_text())
            if expected == 'hash':
                data['camera_sha256'] = {}
            elif expected == 'rack':
                del data['rack_support_source']
            elif expected == 'subtype':
                data['device_subtype'] = 'motorcycle'
            elif expected == 'geometry':
                data['sidewalk_polygon_xy_m'] = [[0, 0], [1, 1], [0, 1], [1, 0]]
            save(path, data)
        try:
            measure(root)
        except ValueError as exc:
            return {'mutation': expected, 'rejected': str(exc)}
        raise AssertionError('Mutation accepted: ' + expected)
    finally:
        path.write_bytes(old)


def main():
    with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
        root = Path(tmp)
        for name in CAMERAS:
            path = root / ('camera_' + name + '.mkv')
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=64x48:r=20',
                            '-frames:v', '600', '-c:v', 'ffv1', str(path)], check=True)
        camera_hashes = {('camera_' + name + '.mkv'): hashlib.sha256(
            (root / ('camera_' + name + '.mkv')).read_bytes()).hexdigest() for name in CAMERAS}
        frame_rows = [{'video_frame': i, 'native_frame': 1000+i, 'time_s': round(i*.05, 4)} for i in range(600)]
        (root/'video_frames.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in frame_rows))
        context = {'assignment_id': AID, 'review_kind': 'synthetic_diagnostic', 'camera_sha256': camera_hashes,
                   'reviewer': 'synthetic-software-test', 'device_subtype': 'bicycle',
                   'device_subtype_source': 'synthetic fixture', 'rack_support_confirmed': True,
                   'rack_support_source': 'synthetic fixture', 'sidewalk_geometry_source': 'synthetic fixture',
                   'pedestrian_corridor_source': 'synthetic fixture', 'operator_join_source': 'synthetic fixture',
                   'parking_state_source': 'synthetic fixture', 'operator_actor_id': 7, 'device_actor_id': 8,
                   'sidewalk_polygon_xy_m': [[-5, -3], [5, -3], [5, 3], [-5, 3]],
                   'rack_polygon_xy_m': [[-1, 1], [1, 1], [1, 2], [-1, 2]],
                   'pedestrian_corridor_polygon_xy_m': [[-5, -1], [5, -1], [5, 1], [-5, 1]]}
        save(root/'parking_context.json', context)
        variants = []
        for name, box, supported in (
                ('rack_clear', [[-.5, 1.2], [.5, 1.2], [.5, 1.8], [-.5, 1.8]], True),
                ('rack_corridor_overlap', [[-.5, .8], [.5, .8], [.5, 1.4], [-.5, 1.4]], True),
                ('outside_rack', [[2, 1.2], [3, 1.2], [3, 1.8], [2, 1.8]], False),
                ('across_path', [[-.5, -.5], [.5, -.5], [.5, .5], [-.5, .5]], False)):
            trace = [{'video_frame': i, 'native_frame': 1000+i, 'source_kind': 'synthetic_native_sample',
                      'device_actor_id': 8, 'operator_actor_id': 7, 'device_speed_mps': 0.0,
                      'device_footprint_xy_m': box} for i in range(600)]
            (root/'native_parking_trace.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in trace))
            observation = measure(root)
            assert (observation['rack_intersection_frame_count'] == 600) == supported
            assert (observation['pedestrian_corridor_intersection_frame_count'] > 0) == (
                name in ('rack_corridor_overlap', 'across_path'))
            variants.append({'name': name, 'rack_intersection_frames': observation['rack_intersection_frame_count'],
                             'corridor_intersection_frames': observation['pedestrian_corridor_intersection_frame_count'],
                             'minimum_corridor_gap_m': observation['minimum_corridor_gap_m_at_rest']})
        negatives = [expect_reject(root, 'native_parking_trace.jsonl', 'frame'),
                     expect_reject(root, 'native_parking_trace.jsonl', 'provenance'),
                     expect_reject(root, 'native_parking_trace.jsonl', 'operator'),
                     expect_reject(root, 'parking_context.json', 'hash'),
                     expect_reject(root, 'parking_context.json', 'rack'),
                     expect_reject(root, 'parking_context.json', 'subtype'),
                     expect_reject(root, 'parking_context.json', 'geometry')]
        print(json.dumps({'assignment_id': AID, 'software_proof': 'synthetic_diagnostic',
                          'variants': variants, 'negative_rejections': negatives,
                          'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
