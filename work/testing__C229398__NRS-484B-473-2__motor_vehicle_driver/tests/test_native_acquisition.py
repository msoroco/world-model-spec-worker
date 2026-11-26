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
from parked_lamps import CASES, ROW_SOURCES
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

    def spawn_vehicle(self, xy):
        return 'vehicle'

    def set_parking_route(self, actor, route, start):
        self.park_start = start

    def set_displayed_lamps(self, actor, mode):
        self.lamp_mode = mode

    def set_auxiliary_lamps(self, actor, mode):
        self.auxiliary_lamp = mode

    def spawn_cameras(self, vehicle, names, scene):
        return {name: name for name in names if not self.missing_camera or name != 'overview'}

    def tick_capture(self, index, scene, cameras):
        row = {'original_frame': 250 + index, 'time_s': 10 + index / 20,
               'vehicle_id': scene['vehicle_id'], 'night': scene['night'],
               'lawful_park': scene['lawful_park'], 'lamp_mode': self.lamp_mode,
               'auxiliary_lamp': self.auxiliary_lamp,
               'speed_mps': 1.0 if index < self.park_start else 0.0,
               'beam_aim_deg': 2.0 if self.lamp_mode == 'undimmed' else -2.0}
        row.update({name + '_source_sha256': scene[name + '_source_sha256']
                    for name in ROW_SOURCES})
        image = Image.new('RGB', (4, 4), color=(30, 40, 50))
        output = BytesIO()
        image.save(output, format='PNG')
        return row, {name: output.getvalue() for name in CAMERAS}

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
        scratch = ROOT / '.runtime-work' / 'c229398-native-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.folder = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def packet(self, case):
        source = self.folder / case.name
        source.mkdir()
        path, data = packet_fixture(source, case)
        data['scene']['park_start_frame'] = 1
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
                                  'overview', 'vehicle'])
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
