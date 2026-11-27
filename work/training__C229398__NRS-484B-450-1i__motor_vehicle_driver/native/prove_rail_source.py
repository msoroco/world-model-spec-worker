"""Diagnostic source-shape and mutation tests for the rail acquisition join."""

import hashlib
import json
import tempfile
from pathlib import Path

from rail_source_contract import CAMERAS, load_original
from rail_footprint_meter import measure

CASE = 'training__C229398__NRS-484B-450-1i__motor_vehicle_driver__selected_98183a3f__condition_a'
SCRATCH = Path(__file__).resolve().parents[3] / '.runtime-work'


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(root, case_id=CASE):
    rails = [{'rail_id': 'west-rail', 'source_kind': 'native_survey',
              'source_ref': 'native-map:rail-west', 'polyline_xy_m': [[0, -10], [0, 10]]},
             {'rail_id': 'east-rail', 'source_kind': 'native_survey',
              'source_ref': 'native-map:rail-east', 'polyline_xy_m': [[1.435, -10], [1.435, 10]]}]
    write(root / 'original-rail-survey.json', {
        'source_kind': 'diagnostic_rail_geometry', 'case_id': case_id,
        'review_status': 'original_geometry_pending_independent_review', 'rails': rails})
    rows, maps = [], []
    for i in range(600):
        native = 1000 + i
        rows.append({'source_kind': 'diagnostic_native_shape', 'case_id': case_id,
                     'native_frame': native, 'video_frame': i, 'time_s': i / 20,
                     'vehicle_actor_id': 42, 'vehicle_center_xy_m': [-12, -3],
                     'vehicle_half_extent_xy_m': [2, 1], 'vehicle_yaw_rad': 0,
                     'pose_source_ref': 'native-actor:42:pose',
                     'extent_source_ref': 'native-actor:42:bounding-box',
                     'speed_source_ref': 'native-actor:42:velocity',
                     'speed_mps': 0, 'halt_reason': 'unknown'})
        maps.append({'native_frame': native, 'video_frame': i, 'time_s': i / 20,
                     'camera_native_frames': {name: native for name in CAMERAS}})
    for name, values in [('original-native-rows.jsonl', rows), ('video_frames.jsonl', maps)]:
        (root / name).write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in values))
    for name in CAMERAS:
        (root / (name + '.mkv')).write_bytes(('synthetic-' + name).encode())
    names = ['original-rail-survey.json', 'original-native-rows.jsonl', 'video_frames.jsonl']
    names += [name + '.mkv' for name in CAMERAS]
    write(root / 'original-source-seal.json', {
        'format': 'diagnostic-rail-source-shape-seal', 'case_id': case_id,
        'sha256': {name: sha(root / name) for name in names}})
    (root / 'trace.jsonl').write_text('synthetic trace shape\n')
    (root / 'capture').mkdir()
    write(root / 'capture/manifest.json', {'case_id': case_id, 'frames': 600,
          'extraction_confirmed': True, 'sources': {'trace.jsonl': sha(root / 'trace.jsonl')}})
    all_names = names + ['original-source-seal.json', 'trace.jsonl', 'capture/manifest.json']
    write(root / 'capture-seal.json', {'format': 'worker-sealed-capture',
          'diagnostic_fixture': True, 'frames': 600, 'restoration': {'restored': True},
          'sources': {name: sha(root / name) for name in all_names}})


def rejects(root, name, edit):
    target = root / name
    old = target.read_bytes()
    try:
        edit(target)
        try:
            load_original(root, CASE)
        except ValueError:
            return True
        raise AssertionError('Altered source accepted: ' + name)
    finally:
        target.write_bytes(old)


def main():
    SCRATCH.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=SCRATCH, prefix='rail-source-') as tmp:
        root = Path(tmp)
        fixture(root)
        packet = load_original(root, CASE)
        assert packet['diagnostic_fixture'] and not packet['original_native_observed']
        result = measure(packet)
        assert len(result['frames']) == 600
        assert all(row['nearest_rail_id'] == 'west-rail' for row in result['frames'])
        assert rejects(root, 'original-rail-survey.json', lambda p: p.write_text('{}\n'))
        assert rejects(root, 'original-native-rows.jsonl', lambda p: p.write_text(p.read_text().replace('"vehicle_actor_id": 42', '"vehicle_actor_id": 0', 1)))
        assert rejects(root, 'video_frames.jsonl', lambda p: p.write_text(p.read_text().replace('"approach": 1000', '"approach": 1001', 1)))
        assert rejects(root, 'overview.mkv', lambda p: p.write_bytes(b'altered-synthetic-video'))
        assert rejects(root, 'trace.jsonl', lambda p: p.write_text('altered trace\n'))
        assert rejects(root, 'capture/manifest.json', lambda p: p.write_text('{}\n'))
        print(json.dumps({'synthetic_fixture': True, 'positive_cases': 1,
                          'altered_diagnostic_source_negatives': 6,
                          'measured_frames': 600,
                          'physical_or_legal_outcome_claimed': False}))


if __name__ == '__main__':
    main()
