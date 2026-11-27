"""Exact source-surveyed alley parking target tests."""
from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alley_width_construction import build_plan
from width_measurement import ASSIGNMENT


def site():
    return {"alley_kind":"other_alley","cul_de_sac":False,"start_connected":True,
            "end_connected":True,"centerline_start_m":[0,2.5],"centerline_end_m":[100,2.5],
            "parking_station_m":50,"cross_sections":[{"station_m":50,
            "left_xy_m":[50,0],"right_xy_m":[50,5]}],
            "ego_length_m":4.5,"ego_width_m":1.8,
            "other_vehicle_blueprint_source":"reviewed:other-blueprint",
            "other_vehicle_dimensions_source":"reviewed:other-dimensions",
            "other_vehicle_length_m":4.2,"other_vehicle_width_m":1.8,
            "ordinance_status":"otherwise_provides"}


class WidthConstructionTests(unittest.TestCase):
    def test_below_at_above_statutory_targets(self):
        for name, target in (("width_9_9ft",9.9),("width_10_0ft",10.0),("width_10_1ft",10.1)):
            with self.subTest(name=name):
                plan=build_plan(site(),ASSIGNMENT+'__'+name)
                self.assertAlmostEqual(plan['planned_available_width_ft'],target,places=4)
                self.assertEqual(plan['capture']['rate_hz'],20)

    def test_both_directions_preserve_width(self):
        cid=ASSIGNMENT+'__width_9_9ft'
        a,b=(build_plan(site(),cid,direction=d) for d in (1,-1))
        self.assertEqual(a['planned_available_width_ft'],b['planned_available_width_ft'])
        self.assertNotEqual(a['start_xy_m'],b['start_xy_m'])

    def test_actual_other_vehicle_target_changes_position(self):
        a=build_plan(site(),ASSIGNMENT+'__other_vehicle_close')
        b=build_plan(site(),ASSIGNMENT+'__other_vehicle_far')
        self.assertIsNotNone(a['other_vehicle_requested_polygon_m'])
        self.assertNotEqual(a['other_vehicle_target_xy_m'],b['other_vehicle_target_xy_m'])
        self.assertAlmostEqual(b['other_vehicle_target_xy_m'][0]-a['other_vehicle_target_xy_m'][0],18)

    def test_ordinance_source_gate(self):
        s=site();s['ordinance_status']='unresolved'
        with self.assertRaisesRegex(ValueError,'ordinance'):
            build_plan(s,ASSIGNMENT+'__ordinance_otherwise')

    def test_unconnected_road_rejected(self):
        s=site();s['end_connected']=False
        with self.assertRaisesRegex(ValueError,'connected'):
            build_plan(s,ASSIGNMENT+'__width_9_9ft')


if __name__=='__main__':
    unittest.main()
