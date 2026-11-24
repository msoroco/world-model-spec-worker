import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from trail import CASES
from trail_capture import capture
from test_source_packet import fixture


class Vehicle:
    id = 42

    def __init__(self, world):
        self.world = world

    def get_transform(self):
        x = -2 if self.world.index < 10 else 1
        location = type('Location', (), {'x': x, 'y': 2})()
        return type('Transform', (), {'location': location})()


class World:
    def __init__(self):
        self.index = -1
        self.settings = type('Settings', (), {'synchronous_mode': True,
                                             'fixed_delta_seconds': .05})()

    def get_settings(self):
        return self.settings

    def get_map(self):
        return type('Map', (), {'to_opendrive': lambda self: '<OpenDRIVE/>\n'})()

    def tick(self):
        self.index += 1
        return 100 + self.index

    def get_snapshot(self):
        return type('Snapshot', (), {'frame': 100 + self.index,
                                     'timestamp': type('Timestamp', (), {
                                         'elapsed_seconds': self.index / 20})()})()


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = World()
        self.vehicle = Vehicle(self.world)
        self.site, self.packet, _ = fixture(self.root, CASES[0])
        self.site['map_sha256'] = hashlib.sha256(self.world.get_map().to_opendrive().encode()).hexdigest()
        self.output = self.root / 'original-history.jsonl'

    def run_capture(self, observer=lambda snapshot, sign: snapshot.frame == 112):
        return capture(self.world, self.vehicle, 'driver-1', observer,
                       self.site, CASES[0], self.packet, self.output, 'camera-plan')

    def test_original_capture_feeds_saved_audit(self):
        result = self.run_capture()
        self.assertEqual(result['frame_count'], 900)
        self.assertTrue(result['entered_corridor'])
        self.assertTrue(result['sign_face_readback'])
        self.assertIsNone(result['legal_judgment'])
        rows = [json.loads(line) for line in self.output.read_text().splitlines()]
        packets = (self.root / 'original-history-packets.jsonl').read_bytes().splitlines(keepends=True)
        self.assertEqual(len(packets), 900)
        self.assertEqual(rows[12]['native_packet_sha256'], hashlib.sha256(packets[12]).hexdigest())
        prior_index = self.world.index
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            self.run_capture()
        self.assertEqual(self.world.index, prior_index)

    def test_source_and_map_gate_before_capture(self):
        (self.root / 'official_plan_designation.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
            self.run_capture()
        self.assertEqual(self.world.index, -1)

    def test_missing_live_sign_readback_rejected(self):
        with self.assertRaisesRegex(ValueError, 'sign face readback'):
            self.run_capture(lambda snapshot, sign: None)
        self.assertFalse(self.output.exists())

    def test_wrong_world_clock_rejected(self):
        self.world.settings.fixed_delta_seconds = .1
        with self.assertRaisesRegex(ValueError, '20 Hz'):
            self.run_capture()
        self.assertEqual(self.world.index, -1)


if __name__ == '__main__':
    unittest.main()
