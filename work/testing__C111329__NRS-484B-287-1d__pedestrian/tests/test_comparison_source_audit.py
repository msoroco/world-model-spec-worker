import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image
from native_acquisition import acquire
from native_crossing import digest
from saved_media_audit import inventory_camera_sources
from saved_process import ASSIGNMENT, process
from comparison_audit import audit_saved_pair
from test_native_acquisition import Adapter, site


class SiteAdapter(Adapter):
    def __init__(self, s):
        super().__init__()
        self.site = s

    def read_devices(self):
        return self.site['devices']

    def camera_png(self, camera, frame):
        im = Image.new('RGB', (4, 3), (frame * 10, len(camera) * 20, 80))
        stream = io.BytesIO()
        im.save(stream, format='PNG')
        return stream.getvalue()


class ComparisonSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, root, name, value):
        raw = (json.dumps(value, sort_keys=True) + '\n').encode()
        (root / name).write_bytes(raw)
        return {'path': name, 'sha256': hashlib.sha256(raw).hexdigest()}

    def attempt(self, suffix, authorized):
        root = self.root / suffix
        root.mkdir()
        s = site()
        if not authorized:
            s['devices'][0]['pedestrian_governance'] = 'straight'
        case_id = ASSIGNMENT + '__' + suffix
        route = 'adjacent' if suffix.startswith('adjacent') else 'opposite'
        packet = acquire(SiteAdapter(s), site=s, site_sha256=digest(s), case_id=case_id,
                         route_kind=route, authorization=authorized,
                         blueprint_id='walker.pedestrian.0001', frames=3, capture_root=root)
        camera = inventory_camera_sources(packet, root)
        refs = [self.write(root, 'site.json', s), self.write(root, 'native.json', packet),
                self.write(root, 'camera.json', camera)]
        process(root, *refs, case_id, root / 'saved.json', expected_frames=3,
                allow_diagnostic=True)
        refs.append({'path': 'saved.json', 'sha256': hashlib.sha256((root / 'saved.json').read_bytes()).hexdigest()})
        return root, refs

    def test_exact_route_and_device_contrasts(self):
        a, ar = self.attempt('adjacent_no_diagonal_authority', False)
        d, dr = self.attempt('diagonal_no_authority', False)
        y, yr = self.attempt('diagonal_authorized', True)
        z, zr = self.attempt('adjacent_authorized_device', True)
        self.assertEqual(audit_saved_pair(a, ar, d, dr, 'diagonal_path_without_authority', expected_frames=3, allow_diagnostic=True)['measured_route_kinds'], ['adjacent', 'opposite'])
        self.assertEqual(audit_saved_pair(d, dr, y, yr, 'diagonal_device_authority', expected_frames=3, allow_diagnostic=True)['observed_diagonal_authorization'], [False, True])
        self.assertEqual(audit_saved_pair(y, yr, z, zr, 'authorized_device_path_control', expected_frames=3, allow_diagnostic=True)['measured_route_kinds'], ['opposite', 'adjacent'])
        with self.assertRaisesRegex(ValueError, 'diagnostic Native'):
            audit_saved_pair(a, ar, d, dr, 'diagonal_path_without_authority', expected_frames=3)
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            audit_saved_pair(d, dr, a, ar, 'diagonal_path_without_authority', expected_frames=3, allow_diagnostic=True)
        (d / 'native.json').write_text('{}\n')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            audit_saved_pair(a, ar, d, dr, 'diagonal_path_without_authority', expected_frames=3, allow_diagnostic=True)


if __name__ == '__main__':
    unittest.main()
