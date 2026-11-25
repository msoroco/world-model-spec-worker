import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location('c158196_officer_capture_sequence',
                                              ROOT / 'officer_capture_sequence.py')
SEQUENCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SEQUENCE)
PREFIX = 'testing__C158196__NRS-484B-257-2__motor_vehicle_driver__'


class Actor:
    def __init__(self, actor_id, x):
        self.id, self.x, self.controls = actor_id, x, []
        self.bounding_box = NS(get_world_vertices=lambda transform:
                               [NS(x=x + dx, y=dy) for dx, dy in
                                ((-1, -1), (-1, 1), (1, -1), (1, 1),
                                 (-1, -1), (-1, 1), (1, -1), (1, 1))])

    def get_transform(self):
        return NS()

    def get_velocity(self):
        return NS(x=0.0, y=0.0, z=0.0)

    def apply_control(self, control):
        self.controls.append(control)


class World:
    def __init__(self):
        self.frame = 0
        self.delta = 0.05

    def get_settings(self):
        return NS(synchronous_mode=True, fixed_delta_seconds=self.delta)

    def tick(self):
        self.frame += 1
        return self.frame

    def get_snapshot(self):
        return NS(frame=self.frame,
                  timestamp=NS(elapsed_seconds=self.frame * self.delta))


class OfficerCaptureSequenceTests(unittest.TestCase):
    def setUp(self):
        self.world = World()
        self.ego, self.other, self.officer = Actor(1, -18), Actor(2, 0), Actor(3, -9)
        self.carla = NS(VehicleControl=lambda **kw: NS(**kw))
        self.reference = {'kind': 'stop_line', 'x_m': -15.0,
                          'source': 'line-reference-site.xodr#stop-line'}
        self.intake = {'format': 'worker-subsection-2-officer-source-intake',
                       'site_id': 'signed-junction', 'officer_source': 'native-walker-3',
                       'site_sha256': '0' * 64}
        self.cameras = lambda frame: {name: {'carla_frame': frame,
                                              'raw_source': name + '/frame-' + str(frame)}
                                      for name in ('overview', 'approach',
                                                   'reference_corner', 'driver_reference')}
        self.adapter = lambda actor, direction: {
            'officer_actor_id': actor.id, 'direction': direction,
            'realized_bones': {'arm': {'pitch': 80.0, 'yaw': 0.0, 'roll': 0.0}}}

    def run_capture(self):
        return SEQUENCE.run(self.carla, self.world, self.ego, self.other,
                            self.officer, self.adapter,
                            PREFIX + 'officer_controls_go', self.reference,
                            self.cameras, self.intake)

    def test_complete_twenty_hertz_capture_and_pose_transition(self):
        capture = self.run_capture()
        self.assertEqual(capture['frame_count'], 600)
        self.assertEqual((capture['first_carla_frame'], capture['last_carla_frame']),
                         (1, 600))
        self.assertEqual(capture['rows'][299]['officer_program']['programmed_direction'],
                         'stop')
        self.assertEqual(capture['rows'][300]['officer_program']['programmed_direction'],
                         'go')
        self.assertAlmostEqual(capture['rows'][-1]['time_s'] -
                               capture['rows'][0]['time_s'], 29.95)
        self.assertEqual(len(self.ego.controls), 600)
        with tempfile.TemporaryDirectory() as directory:
            receipt = SEQUENCE.write_receipt(capture, Path(directory) / 'officer-capture.json')
            self.assertEqual(len(receipt['sha256']), 64)
            self.assertLess(Path(receipt['path']).stat().st_size, 2 * 1024 * 1024)

    def test_rejects_wrong_rate_and_clock_drift(self):
        self.world.delta = 0.1
        with self.assertRaisesRegex(ValueError, 'synchronous 20 Hz'):
            self.run_capture()
        self.world.delta = 0.05
        original = self.world.get_snapshot
        self.world.get_snapshot = lambda: NS(
            frame=self.world.frame,
            timestamp=NS(elapsed_seconds=(self.world.frame * 0.05 +
                                          (0.1 if self.world.frame > 1 else 0))))
        with self.assertRaisesRegex(ValueError, 'rate differs'):
            self.run_capture()
        self.world.get_snapshot = original


if __name__ == '__main__':
    unittest.main()
