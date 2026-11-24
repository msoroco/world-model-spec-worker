import hashlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_acquisition import acquire
from native_crossing import digest
from saved_media_audit import inventory_camera_sources
from saved_process import ASSIGNMENT, process
from test_native_acquisition import Adapter, site

CASE = ASSIGNMENT + '__diagonal_authorized'


class PNGAdapter(Adapter):
    def camera_png(self, camera, frame):
        image = Image.new('RGB', (4, 3), (frame * 20, len(camera) * 25, 80))
        stream = io.BytesIO()
        image.save(stream, format='PNG')
        return stream.getvalue()


class SavedProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.site = site()
        self.packet = acquire(PNGAdapter(), site=self.site,
                              site_sha256=digest(self.site), case_id=CASE,
                              route_kind='opposite', authorization=True,
                              blueprint_id='walker.pedestrian.0001', frames=3,
                              capture_root=self.root)
        self.manifest = inventory_camera_sources(self.packet, self.root)
        self.site_ref = self.write('site.json', self.site)
        self.native_ref = self.write('native.json', self.packet)
        self.camera_ref = self.write('camera-manifest.json', self.manifest)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, obj):
        path = self.root / name
        raw = (json.dumps(obj, sort_keys=True) + '\n').encode()
        path.write_bytes(raw)
        return {'path': name, 'sha256': hashlib.sha256(raw).hexdigest()}

    def run_process(self, **kwargs):
        return process(self.root, self.site_ref, self.native_ref, self.camera_ref,
                       CASE, self.root / 'receipt.json', expected_frames=3,
                       allow_diagnostic=True, **kwargs)

    def test_saved_measurement_and_pixels_join_before_write(self):
        result = self.run_process()
        self.assertEqual(result['media_audit']['decoded_png_count'], 12)
        self.assertEqual(result['measurement']['case_id'], CASE)
        self.assertEqual(result['exception_484B_290'], 'unresolved')
        self.assertIsNone(result['legal_verdict'])
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.run_process()

    def test_changed_original_pixel_prevents_receipt(self):
        path = self.root / self.manifest['sources'][0]['path']
        path.write_bytes(path.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.run_process()
        self.assertFalse((self.root / 'receipt.json').exists())

    def test_rehashed_wrong_case_and_foreign_case_rejected(self):
        self.packet['case_id'] = ASSIGNMENT + '__diagonal_no_authority'
        self.native_ref = self.write('native.json', self.packet)
        with self.assertRaisesRegex(ValueError, 'exact case'):
            self.run_process()
        with self.assertRaisesRegex(ValueError, 'foreign exact'):
            process(self.root, self.site_ref, self.native_ref, self.camera_ref,
                    'foreign__diagonal_authorized', self.root / 'receipt.json',
                    expected_frames=3, allow_diagnostic=True)
        self.assertFalse((self.root / 'receipt.json').exists())


if __name__ == '__main__':
    unittest.main()
