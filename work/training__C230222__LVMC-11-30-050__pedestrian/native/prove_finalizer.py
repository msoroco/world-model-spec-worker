"""Exercise original frame, actor, pose, RGB and source-file rejection paths."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from finalize import report, verify_join


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + '\n')


def rows(path, items):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(item) + '\n' for item in items))


def reject(folder, expected):
    try:
        verify_join(folder, 600)
    except ValueError as exc:
        if expected not in str(exc):
            raise AssertionError(f'Wrong rejection: {exc}') from exc
        return str(exc)
    raise AssertionError('Expected rejection: ' + expected)


def main():
    folder = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve() / 'lvmc-route-finalizer'
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    original = json.loads((HERE.parent / 'draft-route/condition_a/construction.json').read_text())
    config = next(json.loads(item['content']) for item in original['files'] if item['path'] == 'config.json')
    camera_names = [c['name'] for c in config['cameras']]
    samples, mapping, trace, evidence, native = [], [], [], [], []
    for index in range(600):
        frame, time = index + 10, index / 20
        xy = [-3.5 + min(index / 300, 1) * 7, 0]
        hashes = {name: hashlib.sha256((name + str(index)).encode()).hexdigest() for name in camera_names}
        samples.append({'native_frame': frame, 'time_s': time, 'pedestrian_id': 11,
                        'pedestrian_xy_m': xy, 'pedestrian_speed_mps': 0 if index >= 300 else 1.8,
                        'original_frame_sha256': hashes['reference_corner']})
        mapping.append({'video_frame': index, 'native_frame': frame, 'carla_frame': frame,
                        'time_s': time, 'source_rgb_sha256': hashes})
        trace.append({'frame': frame, 'time_s': time})
        evidence.append({'original_frame': frame, 'recording_time_s': time,
                         'ego': {'position_m': [*xy, .5]}})
        native.append({'frame': frame})
    for name, data in (('route-samples.jsonl', samples), ('video_frames.jsonl', mapping),
                       ('trace.jsonl', trace), ('capture/evidence.jsonl', evidence),
                       ('capture/native/frames.jsonl', native)):
        rows(folder / name, data)
    write(folder / 'capture/manifest.json', {'extraction_confirmed': True, 'frames': 600})
    write(folder / 'route-context.json', {'source_kind': 'synthetic_cpu_fixture',
          'expected_frames': 600, 'origin_curb_xy_m': [[-3.5, -20], [-3.5, 20]],
          'opposite_curb_xy_m': [[3.5, -20], [3.5, 20]],
          'crosswalk_polygons_xy_m': [], 'road_geometry_sha256': config['road_geometry_sha256']})
    joined = verify_join(folder, 600)
    positive = report(folder, config['case_id'])
    if positive['measurements']['crossing_route_geometry']['value']['frames'] != 600:
        raise AssertionError('Route report frame count differs')
    negatives = []
    for name, data, index, key, wrong, expected in (
        ('route-samples.jsonl', samples, 100, 'pedestrian_id', 12, 'actor identity changed'),
        ('route-samples.jsonl', samples, 100, 'original_frame_sha256', '0' * 64, 'RGB hash join differs'),
        ('video_frames.jsonl', mapping, 100, 'carla_frame', -1, 'camera frame join differs'),
        ('capture/evidence.jsonl', evidence, 100, 'recording_time_s', -1, 'timestamp join differs')):
        path = folder / name
        altered = copy.deepcopy(data)
        altered[index][key] = wrong
        rows(path, altered)
        negatives.append(reject(folder, expected))
        rows(path, data)
    (folder / 'route-samples.jsonl').unlink()
    try:
        report(folder, config['case_id'])
    except ValueError as exc:
        if 'Missing required source: route-samples.jsonl' not in str(exc):
            raise
        negatives.append(str(exc))
    else:
        raise AssertionError('Missing source accepted')
    output = {'format': 'worker-route-finalizer-cpu-proof-v1', 'joined': joined,
              'source_only_positive': True, 'negative_rejections': negatives,
              'original_native_observed': False,
              'finalizer_sha256': hashlib.sha256((HERE / 'finalize.py').read_bytes()).hexdigest()}
    proof = HERE / 'finalizer-proof.json'
    write(proof, output)
    print(json.dumps({'proof': str(proof), 'negative_rejections': len(negatives),
                      'sha256': hashlib.sha256(proof.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
