"""Source-shaped CPU fixtures for the road-to-driveway sidewalk meter."""

import hashlib
import json
import sys
import tempfile
from pathlib import Path

from measure_sidewalk import CAMERAS, SOURCE_FILES, measure, sha


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
    write_json(folder / 'site-review.json', {
        'source_kind': 'original_site_review',
        'route': 'road_to_private_driveway',
        'district': 'residence',
        'road_xodr_sha256': sha(road),
        'sidewalk_y_interval_m': [0, 2],
        'driveway_connection_reviewed': True,
        'sidewalk_polygon_reviewed': True,
        'pedestrian_route_reviewed': True,
        'fixture_only': True,
    })
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
        native.append({
            'source_kind': 'original_native',
            'native_frame': frame,
            'video_frame': index,
            'time_s': (index + 1) / 20,
            'source_cameras': cameras,
            'vehicle_actor_id': 101,
            'pedestrian_actor_id': 202,
            'vehicle_xy_m': [0.0, y],
            'vehicle_half_extent_m': 1.2,
            'vehicle_speed_mps': speed,
            'pedestrian_xy_m': [8.0 - index * .025, 1.0],
        })
        mappings.append({
            'native_frame': frame,
            'video_frame': index,
            'time_s': (index + 1) / 20,
            'camera_native_frames': cameras,
        })
    write_rows(folder / 'native-rows.jsonl', native)
    write_rows(folder / 'video_frames.jsonl', mappings)
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
            assert result['frame_count'] == 600
            assert result['physical_completion'] is None
            assert result['legal_verdict'] is None
            if suffix == 'stop_before_sidewalk':
                assert result['observed_pre_sidewalk_stop_frames'] > 0
            else:
                assert result['observed_pre_sidewalk_stop_frames'] == 0
            positives.append({'case_id': case_id, 'measurement': result})
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
