import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location('c158196_officer_capture_step',
                                              ROOT / 'officer_capture_step.py')
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)
from stopping_reference import ApproachState


PREFIX = 'testing__C158196__NRS-484B-257-2__motor_vehicle_driver__'


class Actor:
    def __init__(self, actor_id, x):
        self.id, self.x, self.controls = actor_id, x, []
        self.bounding_box = NS(get_world_vertices=lambda transform:
                               [NS(x=self.x + dx, y=dy) for dx, dy in
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
        self.frame = 100

    def tick(self):
        self.frame += 1
        return self.frame


class OfficerCaptureTests(unittest.TestCase):
    def setUp(self):
        self.carla = NS(VehicleControl=lambda **kw: NS(**kw))
        self.world = World()
        self.ego, self.other, self.officer = Actor(1, -18), Actor(2, 0), Actor(3, -9)
        self.reference = {'x_m': -15.0, 'source': 'line-reference-site.xodr#stop-line'}
        self.state = ApproachState()
        self.intake = {'format': 'worker-subsection-2-officer-source-intake',
                       'site_id': 'signed-junction',
                       'officer_source': 'native-walker-actor-3'}
        self.cameras = lambda frame: {name: {'carla_frame': frame,
                                              'raw_source': name + '/frame-101'}
                                      for name in CAPTURE.CAMERAS}
        self.adapter = lambda actor, direction: {
            'officer_actor_id': actor.id, 'direction': direction,
            'realized_bones': {'arm': {'pitch': 80.0, 'yaw': 0.0, 'roll': 0.0}}}

    def capture(self, suffix, frame=0, **kw):
        return CAPTURE.step(self.carla, self.world, self.ego, self.other,
                            self.officer, self.adapter, PREFIX + suffix,
                            frame, 20, self.reference, self.state,
                            self.cameras, self.intake, **kw)

    def test_go_hold_and_inactive_join_original_sources(self):
        go_stop = self.capture('officer_controls_go', 0)
        self.assertEqual(go_stop['ego_control']['command']['brake'], 1.0)
        self.assertEqual(go_stop['officer_direction_observed'], 'unreviewed')
        go = self.capture('officer_controls_go', 11)
        self.assertEqual(go['ego_control']['command']['phase'], 'officer_go_program')
        self.assertEqual(go['officer_program']['realized_bones']['arm']['pitch'], 80.0)
        self.assertEqual(go['carla_frame'], 102)
        self.assertEqual(set(go['camera_raw_sources']), set(CAPTURE.CAMERAS))
        self.assertTrue(go['ego_engineering_stop_before_reference_sample'])
        self.assertEqual(go['stopping_reference']['x_m'], -15.0)
        hold = self.capture('officer_controls_hold', 11)
        self.assertEqual(hold['ego_control']['command']['phase'], 'officer_stop_program')
        inactive = self.capture('officer_present_inactive', 0)
        self.assertEqual(inactive['officer_program']['programmed_direction'], 'none')
        self.assertEqual(inactive['ego_control']['command']['phase'], 'approach')
        self.assertEqual(len(inactive['other_body_vertices_xy_m']), 8)

    def test_rejects_missing_native_source_and_stale_camera(self):
        self.intake['officer_source'] = ''
        with self.assertRaisesRegex(ValueError, 'source intake'):
            self.capture('officer_controls_go')
        self.intake['officer_source'] = 'native-walker-actor-3'
        self.cameras = lambda frame: {name: {'carla_frame': frame - 1,
                                              'raw_source': name + '/stale'}
                                      for name in CAPTURE.CAMERAS}
        with self.assertRaisesRegex(ValueError, 'camera frame mismatch'):
            self.capture('officer_controls_go')
        self.reference = {'source': 'line-site'}
        with self.assertRaisesRegex(ValueError, 'finite stopping reference'):
            self.capture('officer_controls_go')

    def test_rejects_missing_actor_body_and_pose_readback(self):
        self.other.bounding_box.get_world_vertices = lambda transform: []
        with self.assertRaisesRegex(ValueError, 'body missing'):
            self.capture('officer_controls_go')
        self.other = Actor(2, 0)
        self.adapter = lambda actor, direction: None
        with self.assertRaisesRegex(ValueError, 'pose readback missing'):
            self.capture('officer_controls_go')


if __name__ == '__main__':
    unittest.main()
