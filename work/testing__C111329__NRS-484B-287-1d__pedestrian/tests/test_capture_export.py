import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_acquisition import acquire
from native_crossing import digest
from saved_media_audit import inventory_camera_sources
from capture_export import publish
from test_saved_process import PNGAdapter, site


class CaptureExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.site = site()
        self.road = b'<OpenDRIVE><header revMajor="1" revMinor="4" name="diagnostic"/></OpenDRIVE>\n'
        self.site['map_sha256'] = hashlib.sha256(self.road).hexdigest()
        self.packet = acquire(PNGAdapter(), site=self.site, site_sha256=digest(self.site),
                              case_id='testing__C111329__NRS-484B-287-1d__pedestrian__diagonal_authorized',
                              route_kind='opposite', authorization=True,
                              blueprint_id='walker.pedestrian.0001', frames=3,
                              capture_root=self.root)
        self.camera = inventory_camera_sources(self.packet, self.root)
        (self.root / 'construction.json').write_text('{}\n')
        (self.root / 'runner.py').write_text('# diagnostic\n')

    def tearDown(self):
        self.temp.cleanup()

    def test_full_original_layout_and_tamper(self):
        receipt = publish(self.root, packet=self.packet,
                          camera_manifest=self.camera, site=self.site,
                          road_bytes=self.road, restoration_verified=True,
                          expected_frames=3, diagnostic=True)
        self.assertEqual(receipt['frames'], 3)
        self.assertEqual(len((self.root / 'trace.jsonl').read_text().splitlines()), 3)
        self.assertEqual(len((self.root / 'video_frames.jsonl').read_text().splitlines()), 3)
        self.assertEqual(len((self.root / 'capture/native/frames.jsonl').read_text().splitlines()), 3)
        self.assertTrue((self.root / 'overview.mkv').is_file())
        with self.assertRaisesRegex(ValueError, 'already published'):
            publish(self.root, packet=self.packet, camera_manifest=self.camera,
                    site=self.site, road_bytes=self.road, restoration_verified=True,
                    expected_frames=3, diagnostic=True)

    def test_restoration_map_and_pixel_preflight(self):
        with self.assertRaisesRegex(ValueError, 'restoration'):
            publish(self.root, packet=self.packet, camera_manifest=self.camera,
                    site=self.site, road_bytes=self.road,
                    restoration_verified=False, expected_frames=3, diagnostic=True)
        with self.assertRaisesRegex(ValueError, 'OpenDRIVE'):
            publish(self.root, packet=self.packet, camera_manifest=self.camera,
                    site=self.site, road_bytes=b'wrong',
                    restoration_verified=True, expected_frames=3, diagnostic=True)
        path = self.root / self.camera['sources'][0]['path']
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            publish(self.root, packet=self.packet, camera_manifest=self.camera,
                    site=self.site, road_bytes=self.road,
                    restoration_verified=True, expected_frames=3, diagnostic=True)


if __name__ == '__main__':
    unittest.main()
