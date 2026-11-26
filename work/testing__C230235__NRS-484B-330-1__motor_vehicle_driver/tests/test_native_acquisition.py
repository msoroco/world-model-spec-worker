from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from capture_seal import CAMERAS
from flagger_zone import CASES, SOURCES
from native_acquisition import acquire
from test_source_packet import packet_fixture


class FakeNative:
    def __init__(self, *, missing_camera=False):
        self.destroyed = []
        self.restored = False
        self.missing_camera = missing_camera

    def snapshot_settings(self):
        return {'original': True}

    def configure_sync(self, rate_hz):
        self.rate_hz = rate_hz

    def readback_sync(self, rate_hz):
        return self.rate_hz == rate_hz

    def spawn_flagger(self, xy):
        return 'flagger'

    def spawn_vehicle(self, xy):
        return 'vehicle'

    def set_signal(self, actor, signal, start, release):
        self.signal = signal

    def set_route(self, actor, route, response):
        self.response = response

    def spawn_cameras(self, vehicle, names, scene):
        return {name: name for name in names if not self.missing_camera or name != 'overview'}

    def tick_capture(self, index, scene, cameras):
        row = {'original_frame': 250 + index, 'time_s': 10 + index / 20,
               'driver_id': scene['driver_id'], 'vehicle_id': scene['vehicle_id'],
               'flagger_id': scene['flagger_id'], 'designated': scene['designated'],
               'marked_construction': scene['marked_construction'],
               'authorized': scene['authorized'], 'signal': self.signal,
               'signal_visible': True, 'intended_vehicle_id': scene['vehicle_id'],
               'vehicle_speed_mps': 0.0 if self.response == 'stop' and index < 2 else 2.0,
               'vehicle_xy': [float(index), 5.0]}
        row.update({name + '_source_sha256': scene[name + '_source_sha256'] for name in SOURCES})
        image = Image.new('RGB', (4, 4), color=(30, 40, 50))
        bytes_out = BytesIO()
        image.save(bytes_out, format='PNG')
        return row, {name: bytes_out.getvalue() for name in CAMERAS}

    def destroy(self, actor):
        self.destroyed.append(actor)

    def actor_id(self, actor):
        return actor

    def restore_settings(self, settings):
        self.restored = settings == {'original': True}

    def readback_restored(self, settings):
        return self.restored


class NativeOwnerTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / '.runtime-work' / 'c230235-native-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.folder = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def packet(self, case):
        source = self.folder / case.name
        source.mkdir()
        path, data = packet_fixture(source, case)
        data['scene']['signal_frame'] = 0
        data['scene']['release_frame'] = 2
        path.write_text(json.dumps(data) + '\n')
        return path

    def test_all_cases_acquire_synthetic_only_with_restoration(self):
        for case in CASES:
            with self.subTest(case=case.name):
                packet = self.packet(case)
                adapter = FakeNative()
                receipt = acquire(adapter, packet, self.folder / (case.name + '-attempt'),
                                  diagnostic_fixture=True)
                self.assertEqual(receipt['source_frame_count'], 3)
                self.assertEqual(adapter.destroyed,
                                 ['driver_reference', 'reference_corner', 'approach',
                                  'overview', 'vehicle', 'flagger'])
                self.assertTrue(adapter.restored)
                with self.assertRaisesRegex(ValueError, 'provenance'):
                    acquire(FakeNative(), packet, self.folder / (case.name + '-original'))

    def test_incomplete_cameras_restore_world_without_release(self):
        packet = self.packet(CASES[0])
        adapter = FakeNative(missing_camera=True)
        attempt = self.folder / 'attempt'
        with self.assertRaisesRegex(ValueError, 'four original camera'):
            acquire(adapter, packet, attempt, diagnostic_fixture=True)
        self.assertTrue(adapter.restored)
        self.assertFalse((attempt / 'native-owner-release.json').exists())


if __name__ == '__main__':
    unittest.main()
