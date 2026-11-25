import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import officer_capture_step as CAPTURE


class OfficerCaptureStepTests(unittest.TestCase):
    def fixtures(self):
        applied = []
        ego = NS(id=11, get_velocity=lambda: NS(x=0.0, y=0.0, z=0.0),
                 apply_control=lambda control: applied.append(control))
        officer = NS(id=12)
        carla = NS(VehicleControl=lambda **values: NS(**values))
        world = NS(tick=lambda: 1234)
        adapter = lambda actor, direction: {'officer_actor_id': actor.id,
                                             'direction': direction,
                                             'realized_bones': {'arm': {'yaw': 10.0}}}
        cameras = lambda frame: {name: {'carla_frame': frame,
                                        'raw_source': name + '.mkv#frame-1234'}
                                 for name in CAPTURE.CAMERAS}
        traffic = {'source': 'other-history.jsonl#frame-1233',
                   'other_inside': True, 'approaching_hazard': False,
                   'site_id': 'test-site', 'other_actor_id': 33,
                   'other_body_vertices_xy_m': [[0, 0], [1, 0], [1, 1], [0, 1]],
                   'hazard_source': 'hazard-review.json#frame-1233'}
        intake = {'format': 'worker-officer-subsection-2-source-intake',
                  'site_id': 'test-site'}
        return carla, world, ego, officer, adapter, cameras, traffic, intake, applied

    def test_exact_tick_binds_four_raw_cameras_without_claiming_control(self):
        carla, world, ego, officer, adapter, cameras, traffic, intake, applied = self.fixtures()
        case = 'testing__C157964__NRS-484B-257-2__motor_vehicle_driver__officer_controls_go'
        result = CAPTURE.step(carla, world, ego, officer, adapter, case, 3, 10,
                              traffic, cameras, intake)
        self.assertEqual(result['carla_frame'], 1234)
        self.assertEqual(set(result['camera_raw_sources']), set(CAPTURE.CAMERAS))
        self.assertEqual(result['officer_direction_observed'], 'unreviewed')
        self.assertEqual(result['actual_police_control_observed'], 'unreviewed')
        self.assertEqual(result['officer_program']['programmed_direction'], 'stop')
        self.assertEqual(applied[0].brake, 1.0)

    def test_missing_camera_or_traffic_source_rejected(self):
        carla, world, ego, officer, adapter, cameras, traffic, intake, _ = self.fixtures()
        case = 'testing__C157964__NRS-484B-257-2__motor_vehicle_driver__officer_present_inactive'
        with self.assertRaisesRegex(ValueError, 'Original other-traffic source'):
            CAPTURE.step(carla, world, ego, officer, adapter, case, 1, 10,
                         {**traffic, 'source': ''}, cameras, intake)
        with self.assertRaisesRegex(ValueError, 'Four original camera frames'):
            CAPTURE.step(carla, world, ego, officer, adapter, case, 1, 10,
                         traffic, lambda frame: {}, intake)
        with self.assertRaisesRegex(ValueError, 'Original camera frame mismatch'):
            CAPTURE.step(carla, world, ego, officer, adapter, case, 1, 10,
                         traffic, lambda frame: {name: {'carla_frame': frame - 1,
                                                         'raw_source': 'source'}
                                                 for name in CAPTURE.CAMERAS}, intake)
        with self.assertRaisesRegex(ValueError, 'Reviewed officer site intake'):
            CAPTURE.step(carla, world, ego, officer, adapter, case, 1, 10,
                         traffic, cameras, {})
        with self.assertRaisesRegex(ValueError, 'Native other body and hazard source binding'):
            CAPTURE.step(carla, world, ego, officer, adapter, case, 1, 10,
                         {**traffic, 'hazard_source': ''}, cameras, intake)

    def test_physical_speed_setpoint_changes_native_throttle(self):
        carla, world, ego, officer, adapter, cameras, traffic, intake, applied = self.fixtures()
        case = 'testing__C157964__NRS-484B-257-2__motor_vehicle_driver__officer_controls_go'
        CAPTURE.step(carla, world, ego, officer, adapter, case, 6, 10,
                     traffic, cameras, intake, target_speed_mps=1.0)
        CAPTURE.step(carla, world, ego, officer, adapter, case, 6, 10,
                     traffic, cameras, intake, target_speed_mps=3.0)
        self.assertEqual([round(control.throttle, 3) for control in applied], [0.25, 0.6])

    def test_hold_release_changes_native_brake_after_go(self):
        carla, world, ego, officer, adapter, cameras, traffic, intake, applied = self.fixtures()
        case = 'testing__C157964__NRS-484B-257-2__motor_vehicle_driver__c157964_sub2_judgment_2-0000'
        CAPTURE.step(carla, world, ego, officer, adapter, case, 6, 10,
                     traffic, cameras, intake, ego_hold_until_frame=8)
        CAPTURE.step(carla, world, ego, officer, adapter, case, 8, 10,
                     traffic, cameras, intake, ego_hold_until_frame=8)
        self.assertEqual((applied[0].brake, applied[1].throttle), (1.0, 0.6))
        with self.assertRaisesRegex(ValueError, 'Ego hold release frame outside'):
            CAPTURE.step(carla, world, ego, officer, adapter, case, 8, 10,
                         traffic, cameras, intake, ego_hold_until_frame=10)


if __name__ == '__main__':
    unittest.main()
