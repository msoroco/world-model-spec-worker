"""CPU geometry and source qualification tests; no CARLA or physical acceptance."""
import json
import unittest
from pathlib import Path
from package_spec import AID,CAMERA_NAMES,CELL,LAW
from scooter_785 import CASES,SOURCE_ROLES,qualifying_device,validate_scene


def scene_for(case):
    y=1.75
    lane=[0,0,350,3] if case.in_lane else [0,3,350,6]
    device={'device_id':'test-electric-scooter','handlebars':True,'electric_motor':True,
            'upright_or_seated':'upright','propulsion':'motor_and_rider',
            'rider_excluded_weight_lb':75 if case.qualifies else 110,
            'motor_only_max_speed_mph':19,
            'manufacturer_assistive_device_intent':False}
    scene={'assignment_id':AID,'cell_id':CELL,'actor':'cycle_or_scooter_operator',
           'facility_kind':'official_bicycle_lane','bicycle_lane_rect_m':lane,
           'roadway_rect_m':[0,0,350,6],
           'lane_designation_id':'reviewed-test-lane','jurisdiction':'reviewed-test-jurisdiction',
           'ordinance_context':case.ordinance,'ordinance_effect_judgment':None,
           'ordinance_enacted_under_nrs_484a_469':case.ordinance=='reviewed_ordinance',
           'ordinance_effective_date':'reviewed-date' if case.ordinance=='reviewed_ordinance' else None,
           'ordinance_text_sha256':'b'*64 if case.ordinance=='reviewed_ordinance' else None,
           'device':device,'ego_route_xy':[[0,y],[350,y]]}
    scene.update({role+'_source_sha256':'a'*64 for role in SOURCE_ROLES})
    return scene


class ScooterBundleTests(unittest.TestCase):
    def test_exact_config_and_cases(self):
        cfg=json.loads(Path('config.json').read_text())
        self.assertEqual((cfg['law_id'],cfg['cell_id'],cfg['actor']),
                         (LAW,CELL,'cycle_or_scooter_operator'))
        self.assertEqual(set(cfg['supported_case_ids']),
                         {AID+'__'+case.name for case in CASES})
        self.assertEqual(tuple(camera['name'] for camera in cfg['cameras']),CAMERA_NAMES)
        self.assertEqual((cfg['rate_hz'],cfg['duration_s']),(20,45))

    def test_each_exact_scene_and_source_rejections(self):
        for case in CASES:
            scene=scene_for(case)
            self.assertEqual(validate_scene(scene,case)['case_id'],AID+'__'+case.name)
            self.assertIs(qualifying_device(scene['device']),case.qualifies)
            bad=dict(scene,lane_designation_id='')
            with self.assertRaisesRegex(ValueError,'official bicycle lane'):
                validate_scene(bad,case)
            bad=dict(scene,ego_route_xy=[[0,5.0],[350,5.0]] if case.in_lane else
                                         [[0,4.0],[350,4.0]])
            with self.assertRaisesRegex(ValueError,'route does not match'):
                validate_scene(bad,case)
            if case.ordinance=='reviewed_ordinance':
                bad=dict(scene,ordinance_text_sha256=None)
                with self.assertRaisesRegex(ValueError,'enacted ordinance'):
                    validate_scene(bad,case)


if __name__=='__main__':
    unittest.main()
