"""Source-shaped CPU fixtures for the road-to-driveway sidewalk meter."""

import hashlib
import json
import sys
import tempfile
from pathlib import Path

from measure_sidewalk import CAMERAS, SITE_SOURCES, SOURCE_FILES, measure, measure_core_join, sha


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent.name


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def write_rows(path, values):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in values))


def fixture(folder, suffix):
    case_id = ASSIGNMENT + '__' + suffix
    road = folder / 'road.xodr'
    road.write_text('<OpenDRIVE><header name="C213851 diagnostic road-to-driveway"/></OpenDRIVE>\n')
    (folder / 'site-sources').mkdir()
    source_refs = {}
    for key, name in SITE_SOURCES.items():
        write_json(folder / name, {'fixture_only': True, 'review_item': key})
        source_refs[key] = {'path': name, 'sha256': sha(folder / name)}
    review = {
        'source_kind': 'original_site_review',
        'route': 'road_to_private_driveway',
        'district': 'residence',
        'road_xodr_sha256': sha(road),
        'sidewalk_y_interval_m': [0, 2],
        'world_sidewalk_y_interval_m': [-5.5, -3.5],
        'route_frame': 'road_east_then_driveway_south',
        'driveway_connection_reviewed': True,
        'sidewalk_polygon_reviewed': True,
        'pedestrian_route_reviewed': True,
        'fixture_only': True,
        **source_refs,
    }
    write_json(folder / 'original-site-review.json', review)
    write_json(folder / 'site-review.json', review)
    for name in CAMERAS:
        (folder / (name + '.mkv')).write_text('CPU source marker for ' + name + '\n')
    native = []
    mappings = []
    for index in range(600):
        frame = 1100 + index
        if suffix == 'stop_before_sidewalk':
            y = -8 + min(index, 180) * .035
            if index > 250:
                y += (index - 250) * .04
            speed = 0.0 if 180 <= index <= 250 else .78
        else:
            y = -8 + index * .04
            speed = .8
        cameras = {name: frame for name in CAMERAS}
        world_vehicle = ([y + 1.75, -1.75] if y < -1.75
                         else [0.0, -3.5 - y])
        ped_x = 8.0 - index * .025
        native.append({
            'source_kind': 'original_native',
            'native_frame': frame,
            'video_frame': index,
            'time_s': (index + 1) / 20,
            'source_cameras': cameras,
            'vehicle_actor_id': 101,
            'pedestrian_actor_id': 202,
            'vehicle_xy_m': [0.0, y],
            'vehicle_world_xy_m': world_vehicle,
            'vehicle_half_extent_m': 1.2,
            'vehicle_speed_mps': speed,
            'pedestrian_xy_m': [ped_x, 1.0],
            'pedestrian_world_xy_m': [ped_x, -4.5],
        })
        mappings.append({
            'native_frame': frame,
            'video_frame': index,
            'time_s': (index + 1) / 20,
            'camera_native_frames': cameras,
        })
    write_rows(folder / 'native-rows.jsonl', native)
    write_rows(folder / 'video_frames.jsonl', mappings)
    capture = folder / 'capture'
    (capture / 'native').mkdir(parents=True)
    write_rows(folder / 'trace.jsonl', [
        {'frame': row['native_frame'], 'time_s': row['time_s'],
         'position': {'x': row['vehicle_world_xy_m'][0],
                      'y': row['vehicle_world_xy_m'][1]},
         'speed_mps': row['vehicle_speed_mps']} for row in native])
    write_rows(capture / 'evidence.jsonl', [
        {'original_frame': row['native_frame'],
         'recording_time_s': row['time_s'],
         'ego': {'position_m': row['vehicle_world_xy_m'],
                 'speed_mps': row['vehicle_speed_mps']}} for row in native])
    write_rows(capture / 'native/frames.jsonl', [
        {'frame': row['native_frame'], 'time_s': row['time_s']}
        for row in native])
    write_json(folder / 'captured-source-hashes.json', {
        'format': 'original-native-sidewalk-source-seal',
        'case_id': case_id,
        'source_kind': 'original_native_capture',
        'sha256': {name: sha(folder / name) for name in SOURCE_FILES},
        'fixture_only': True,
    })
    return case_id


def reseal(folder):
    seal_path = folder / 'captured-source-hashes.json'
    seal = json.loads(seal_path.read_text())
    seal['sha256'] = {name: sha(folder / name) for name in SOURCE_FILES}
    write_json(seal_path, seal)


def reject(folder, case_id, expected):
    try:
        measure(folder, case_id)
    except ValueError as exc:
        if expected not in str(exc):
            raise AssertionError(str(exc)) from exc
        return str(exc)
    raise AssertionError('Changed source was accepted: ' + expected)


def main():
    positives = []
    negatives = []
    with tempfile.TemporaryDirectory(prefix='c213851-sidewalk-') as tmp:
        root = Path(tmp)
        for suffix in ('stop_before_sidewalk', 'cross_without_stop'):
            folder = root / suffix
            folder.mkdir()
            case_id = fixture(folder, suffix)
            result = measure(folder, case_id)
            core_result = measure_core_join(folder, case_id)
            assert core_result['core_join']['original_native_core_join_passed'] is True
            assert result['frame_count'] == 600
            assert result['physical_completion'] is None
            assert result['legal_verdict'] is None
            if suffix == 'stop_before_sidewalk':
                assert result['observed_pre_sidewalk_stop_frames'] > 0
            else:
                assert result['observed_pre_sidewalk_stop_frames'] == 0
            positives.append({'case_id': case_id, 'measurement': result})
            core_trace = folder / 'trace.jsonl'
            core_data = core_trace.read_bytes()
            core_trace.unlink()
            try:
                measure_core_join(folder, case_id)
            except ValueError as exc:
                assert 'Missing required source' in str(exc)
                negatives.append({'case_id': case_id, 'error': str(exc)})
            else:
                raise AssertionError('Missing Core source was accepted')
            core_trace.write_bytes(core_data)
            original_source = folder / SITE_SOURCES['sidewalk_source']
            source_data = original_source.read_bytes()
            original_source.unlink()
            negatives.append({'case_id': case_id, 'error': reject(folder, case_id, 'missing or changed')})
            original_source.write_bytes(source_data)
            missing = folder / 'site-review.json'
            data = missing.read_bytes()
            missing.unlink()
            negatives.append({'case_id': case_id, 'error': reject(folder, case_id, 'missing or changed')})
            missing.write_bytes(data)
            row_path = folder / 'native-rows.jsonl'
            rows = [json.loads(line) for line in row_path.read_text().splitlines()]
            rows[10]['vehicle_speed_mps'] = True
            write_rows(row_path, rows)
            reseal(folder)
            negatives.append({'case_id': case_id, 'error': reject(folder, case_id, 'motion differs')})
            rows[10]['vehicle_speed_mps'] = .8
            write_rows(row_path, rows)
            rows[12]['source_cameras']['overview'] = 999
            write_rows(row_path, rows)
            reseal(folder)
            negatives.append({'case_id': case_id, 'error': reject(folder, case_id, 'frame join differs')})
    proof = {'format': 'road-to-driveway-source-shape-proof',
             'passed': True, 'positive_count': len(positives),
             'negative_count': len(negatives), 'positives': positives,
             'negatives': negatives, 'actual_original_capture_observed': False,
             'legal_verdict_claimed': False}
    path = HERE / 'sidewalk-source-shape-proof.json'
    write_json(path, proof)
    print(json.dumps({'passed': True, 'positive_count': len(positives),
                      'negative_count': len(negatives), 'proof_sha256': sha(path)}))


if __name__ == '__main__':
    main()
