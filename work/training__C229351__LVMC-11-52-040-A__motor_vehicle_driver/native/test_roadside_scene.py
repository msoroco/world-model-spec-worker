import copy
import unittest
from pathlib import Path

from roadside_scene import check
from selected_plan import CASES


HERE = Path(__file__).resolve().parent
CAMERAS = [
    {'name': name, 'width': width, 'height': height, 'fps': 20,
     'fov_deg': 85, 'pose_strategy': 'ego_follow' if name == 'driver_reference' else 'world_static',
     'location_xyz_m': [0, 0, 2], 'rotation_pyr_deg': [0, 0, 0]}
    for name, width, height in (('overview', 1920, 1080), ('approach', 1280, 720),
                                ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))]


def config(case):
    setting = CASES[case]
    return {'case_id': case, 'selected_case_id': case,
            'law_id': 'LVMC-11-52-040-A', 'cell_id': 'C229351',
            'actor': 'motor_vehicle_driver', 'layout': 'road',
            'maneuver': 'parallel_park', 'control': 'road_edge',
            'duration_s': 30, 'rate_hz': 20, 'duration_frames': 600,
            'supported_case_ids': list(CASES),
            'activity_requested': setting['activity'],
            'rest_pose_requested': setting['pose'],
            'requested_yaw_offset_deg': setting['requested_yaw_offset_deg'],
            'requested_rest_center_x_m': 4.2, 'controller_mode': 'service_brake',
            'required_atoms': ['kin.heading', 'kin.speed'], 'cameras': CAMERAS}


class SceneTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.road = (HERE / 'road-edge-road.xodr').read_text()

    def test_six_exact_roadway_poses(self):
        self.assertEqual(len(CASES), 6)
        for case in CASES:
            with self.subTest(case=case):
                result = check(config(case), self.road)
                self.assertTrue(result['authored_footprint_inside_driving_roadway'])
                self.assertFalse(result['original_native_observed'])

    def test_scope_and_edge_rejections(self):
        case = next(iter(CASES))
        for key, value, error in (('duration_frames', 599, 'window'),
                                  ('requested_yaw_offset_deg', 35, 'orientation'),
                                  ('requested_rest_center_x_m', 6.8, 'footprint'),
                                  ('controller_mode', 'coast', 'controller')):
            with self.subTest(key=key):
                changed = copy.deepcopy(config(case))
                changed[key] = value
                with self.assertRaisesRegex(ValueError, error):
                    check(changed, self.road)


if __name__ == '__main__':
    unittest.main()
