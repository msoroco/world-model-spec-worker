"""Four source-shape variants and negative joins for saved adjacent-path measurement."""
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from measure_path import AID, CAMERAS, measure


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def reject(root, name, mutation):
    target = root/name
    original = target.read_bytes()
    try:
        if name.endswith('.jsonl'):
            rows = target.read_text().splitlines()
            row = json.loads(rows[0])
            if mutation == 'frame':
                row['native_frame'] += 10
            elif mutation == 'provenance':
                row['source_kind'] = 'original_native_pose'
            elif mutation == 'rider':
                row['rider_actor_id'] = 99
            rows[0] = json.dumps(row)
            target.write_text('\n'.join(rows)+'\n')
        else:
            data = json.loads(target.read_text())
            if mutation == 'camera_hash':
                data['camera_sha256'] = {}
            elif mutation == 'surface_source':
                del data['path_surface_source']
            elif mutation == 'subtype':
                data['device_subtype'] = 'motorcycle'
            elif mutation == 'overlap_geometry':
                data['roadway_polygon_xy_m'] = data['path_polygon_xy_m']
            elif mutation == 'usability':
                del data['path_usable_reviewed']
            save(target, data)
        try:
            measure(root)
        except ValueError as exc:
            return {'mutation': mutation, 'rejected': str(exc)}
        raise AssertionError('Mutation accepted: '+mutation)
    finally:
        target.write_bytes(original)


def main():
    with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
        root = Path(tmp)
        for name in CAMERAS:
            video = root/(name+'.mkv')
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=64x48:r=20',
                            '-frames:v', '600', '-c:v', 'ffv1', str(video)], check=True)
        hashes = {(name+'.mkv'): hashlib.sha256((root/(name+'.mkv')).read_bytes()).hexdigest()
                  for name in CAMERAS}
        frames = [{'video_frame': i, 'native_frame': 1000+i, 'time_s': round(i*.05, 4)} for i in range(600)]
        (root/'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in frames))
        context = {'assignment_id': AID, 'review_kind': 'synthetic_diagnostic', 'camera_sha256': hashes,
                   'reviewer': 'synthetic-software-test', 'device_subtype': 'bicycle',
                   'device_subtype_source': 'synthetic fixture', 'rider_identity_source': 'synthetic fixture',
                   'path_surface_source': 'synthetic fixture', 'path_continuity_source': 'synthetic fixture',
                   'path_adjacency_source': 'synthetic fixture', 'path_obstruction_source': 'synthetic fixture',
                   'path_usability_review_source': 'synthetic fixture', 'roadway_boundary_source': 'synthetic fixture',
                   'path_continuous': True, 'path_adjacent': True, 'path_usable_reviewed': True,
                   'path_context': {'path_continuous': True, 'path_adjacent': True,
                                    'path_usable_reviewed': True, 'source_kind': 'synthetic_diagnostic'},
                   'rider_actor_id': 7, 'device_actor_id': 8,
                   'path_polygon_xy_m': [[0, 2], [100, 2], [100, 4], [0, 4]],
                   'roadway_polygon_xy_m': [[0, -4], [100, -4], [100, 0], [0, 0]],
                   'path_obstruction_polygon_xy_m': [[30, 5], [31, 5], [31, 6], [30, 6]]}
        save(root/'path_context.json', context)
        variants = []
        for label, y, obstruction in (('path_clear', 3.0, False),
                                      ('roadway_with_path', -2.0, False),
                                      ('path_obstructed', 3.0, True),
                                      ('outside_both', 1.0, False)):
            if obstruction:
                context['path_obstruction_polygon_xy_m'] = [[30, 2.5], [31, 2.5], [31, 3.5], [30, 3.5]]
                context['path_usable_reviewed'] = False
                context['path_context']['path_usable_reviewed'] = False
            else:
                context['path_obstruction_polygon_xy_m'] = [[30, 5], [31, 5], [31, 6], [30, 6]]
                context['path_usable_reviewed'] = True
                context['path_context']['path_usable_reviewed'] = True
            save(root/'path_context.json', context)
            trace = [{'video_frame': i, 'native_frame': 1000+i, 'source_kind': 'synthetic_native_sample',
                      'rider_actor_id': 7, 'device_actor_id': 8, 'device_speed_mps': 3.0,
                      'device_footprint_xy_m': [[i*.1, y-.2], [i*.1+.6, y-.2],
                                                [i*.1+.6, y+.2], [i*.1, y+.2]]} for i in range(600)]
            (root/'native_rider_trace.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in trace))
            observed = measure(root)
            assert (observed['path_occupancy_moving_frames'] == 600) == (label in ('path_clear', 'path_obstructed'))
            assert (observed['roadway_occupancy_moving_frames'] == 600) == (label == 'roadway_with_path')
            assert (observed['outside_both_moving_frames'] == 600) == (label == 'outside_both')
            variants.append({'name': label, 'path_frames': observed['path_occupancy_moving_frames'],
                             'road_frames': observed['roadway_occupancy_moving_frames'],
                             'obstruction_area_m2': observed['path_obstruction_intersection_area_m2'],
                             'usable_reviewed': observed['path_usable_reviewed']})
        negatives = [reject(root, 'native_rider_trace.jsonl', 'frame'),
                     reject(root, 'native_rider_trace.jsonl', 'provenance'),
                     reject(root, 'native_rider_trace.jsonl', 'rider'),
                     reject(root, 'path_context.json', 'camera_hash'),
                     reject(root, 'path_context.json', 'surface_source'),
                     reject(root, 'path_context.json', 'subtype'),
                     reject(root, 'path_context.json', 'overlap_geometry'),
                     reject(root, 'path_context.json', 'usability')]
        print(json.dumps({'assignment_id': AID, 'software_proof': 'synthetic_diagnostic',
                          'variants': variants, 'negative_rejections': negatives,
                          'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
