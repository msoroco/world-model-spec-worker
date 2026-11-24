import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from test_departure_geometry import packet

spec = importlib.util.spec_from_file_location('departure_saved_delivery', Path(__file__).resolve().parents[1] / 'saved_delivery.py')
saved = importlib.util.module_from_spec(spec)
spec.loader.exec_module(saved)
CASE = 'testing__C109705__NRS-484B-400-2b__motor_vehicle_driver__near_centerline'


def write(root, relative, content):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    return {'path': relative, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def fixture(root):
    map_data, trace = packet()
    source = write(root, 'original/map.xodr', '<OpenDRIVE/>\n')
    map_data['source_path'] = source['path']
    map_data['source_sha256'] = source['sha256']
    corners = [[1, 5], [2, 5], [2, 7], [1, 7]]
    trace['samples'] = []
    for frame in range(900):
        phase = 'approach' if frame < 100 else ('intersection_entry' if frame == 100 else
                                                'turning' if frame < 400 else 'departure')
        row = {'frame': frame, 'phase': phase}
        if phase == 'departure':
            row.update(road_id=4, body_corners_xy_m=corners)
        trace['samples'].append(row)
    channels = {}
    for name in saved.CAMERAS:
        camera = write(root, f'original/{name}.media', f'original {name} bytes\n')
        channels[name] = [{'frame': frame, 'channel': name,
                           'source_path': camera['path'],
                           'source_sha256': camera['sha256']} for frame in range(900)]
    manifest = {
        'case_id': CASE, 'acquisition_kind': 'diagnostic_fixture',
        'duration_s': 45, 'rate_hz': 20,
        'map': write(root, 'original/map-packet.json', json.dumps(map_data)),
        'trace': write(root, 'original/trace.json', json.dumps(trace)),
        'camera_index': write(root, 'original/camera-index.json',
                              json.dumps({'case_id': CASE, 'channels': channels})),
    }
    return manifest


def replace_json(root, manifest, key, change):
    path = root / manifest[key]['path']
    value = json.loads(path.read_text())
    change(value)
    manifest[key] = write(root, manifest[key]['path'], json.dumps(value))


class SavedDeliveryTests(unittest.TestCase):
    def test_full_source_integrity_and_diagnostic_caveat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fixture(root)
            out = saved.audit(root, manifest, case_id=CASE, allow_diagnostic=True)
            self.assertEqual(out['source_integrity'], 'passed')
            self.assertEqual(out['original_frames'], 900)
            self.assertEqual(out['source_file_count'], 4)
            self.assertEqual(out['departure_measurement']['sample_count'], 500)
            self.assertFalse(out['actual_pixels'])
            self.assertFalse(out['physical_completion'])
            with self.assertRaisesRegex(ValueError, 'original Native acquisition'):
                saved.audit(root, manifest, case_id=CASE)

    def test_missing_camera_frame_and_tampered_media_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fixture(root)
            replace_json(root, manifest, 'camera_index', lambda value: value['channels']['left'].pop())
            with self.assertRaisesRegex(ValueError, '900 original camera'):
                saved.audit(root, manifest, case_id=CASE, allow_diagnostic=True)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fixture(root)
            (root / 'original' / 'right.media').write_text('replaced\n')
            with self.assertRaisesRegex(ValueError, 'source hash differs'):
                saved.audit(root, manifest, case_id=CASE, allow_diagnostic=True)

    def test_context_frame_case_and_path_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fixture(root)
            replace_json(root, manifest, 'trace', lambda value: value['samples'][100].update(frame=101))
            with self.assertRaisesRegex(ValueError, 'strictly increasing|900 consecutive'):
                saved.audit(root, manifest, case_id=CASE, allow_diagnostic=True)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fixture(root)
            manifest['case_id'] = CASE + '_wrong'
            with self.assertRaisesRegex(ValueError, 'case identity'):
                saved.audit(root, manifest, case_id=CASE, allow_diagnostic=True)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fixture(root)
            manifest['map']['path'] = '../escaped.json'
            with self.assertRaisesRegex(ValueError, 'escapes attempt'):
                saved.audit(root, manifest, case_id=CASE, allow_diagnostic=True)

    def test_centerline_and_original_map_hash_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fixture(root)
            replace_json(root, manifest, 'map', lambda value: value.update(centerline_kind='source_derived_imaginary'))
            with self.assertRaisesRegex(ValueError, 'centerline convention'):
                saved.audit(root, manifest, case_id=CASE, allow_diagnostic=True)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fixture(root)
            (root / 'original' / 'map.xodr').write_text('<Changed/>\n')
            with self.assertRaisesRegex(ValueError, 'original map source hash differs'):
                saved.audit(root, manifest, case_id=CASE, allow_diagnostic=True)


if __name__ == '__main__':
    unittest.main()
