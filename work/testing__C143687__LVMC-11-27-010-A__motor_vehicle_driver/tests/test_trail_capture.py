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
from saved_audit import audit_packet_join
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
        scratch = PACKAGE.parents[1] / '.runtime-work' / 'c143687-packet-join-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = World()
        self.vehicle = Vehicle(self.world)
        self.site, self.packet, packet = fixture(self.root, CASES[0])
        map_bytes = self.world.get_map().to_opendrive().encode()
        (self.root / 'map.txt').write_bytes(map_bytes)
        self.site['map_sha256'] = hashlib.sha256(map_bytes).hexdigest()
        packet['sources']['map']['sha256'] = self.site['map_sha256']
        self.packet.write_text(json.dumps(packet), encoding='utf-8')
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

    def test_native_control_and_camera_callbacks_share_original_frames(self):
        controls, cameras = [], []
        capture(self.world, self.vehicle, 'driver-1',
                lambda snapshot, sign: snapshot.frame == 112,
                self.site, CASES[0], self.packet, self.output, 'camera-plan',
                before_tick=lambda vehicle, site, index: controls.append((index, self.world.index)),
                on_frame=lambda sample, snapshot: cameras.append((sample['frame'], snapshot.frame)))
        self.assertEqual(len(controls), 900)
        self.assertEqual(controls[0], (0, -1))
        self.assertEqual(controls[-1], (899, 898))
        self.assertEqual(cameras, [(100 + index, 100 + index) for index in range(900)])

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

    def test_saved_original_packet_join_and_tamper(self):
        self.run_capture()
        history = self.output
        packets = self.root / 'original-history-packets.jsonl'
        hdigest = hashlib.sha256(history.read_bytes()).hexdigest()
        pdigest = hashlib.sha256(packets.read_bytes()).hexdigest()
        report = audit_packet_join(history, hdigest, packets, pdigest,
                                   self.site['corridor_box_xy'],
                                   'testing__C143687__LVMC-11-27-010-A__motor_vehicle_driver__all_prerequisites')
        self.assertEqual(report['joined_frames'], 900)
        self.assertTrue(report['entered_corridor'])
        self.assertFalse(report['physical_video_visibility_verified'])
        with packets.open('ab') as stream:
            stream.write(b'changed\n')
        with self.assertRaisesRegex(ValueError, 'packet stream hash mismatch'):
            audit_packet_join(history, hdigest, packets, pdigest,
                              self.site['corridor_box_xy'], report['case_id'])

    def test_resealed_history_corridor_observation_rejected(self):
        self.run_capture()
        history = self.output
        packets = self.root / 'original-history-packets.jsonl'
        rows = [json.loads(line) for line in history.read_text().splitlines()]
        rows[15]['vehicle_inside_corridor'] = False
        history.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaisesRegex(ValueError, 'corridor observation mismatch'):
            audit_packet_join(history, hashlib.sha256(history.read_bytes()).hexdigest(),
                              packets, hashlib.sha256(packets.read_bytes()).hexdigest(),
                              self.site['corridor_box_xy'],
                              'testing__C143687__LVMC-11-27-010-A__motor_vehicle_driver__all_prerequisites')


if __name__ == '__main__':
    unittest.main()
