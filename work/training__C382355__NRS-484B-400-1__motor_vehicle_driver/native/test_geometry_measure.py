import json
from pathlib import Path
import tempfile
import unittest

from geometry import CASE_APPROACH_Y_M,check,route
from measure_lane import measure


def sample(frame,time,x,y,road,lane,forward):
    hx,hy=(2.6,1.1) if forward==[1,0] else (1.1,2.6)
    return {'native_frame':frame,'time_s':time,'native_road_id':road,'native_lane_id':lane,
            'native_forward_xy':forward,'native_body_xy_m':
            [[x-hx,y-hy],[x-hx,y+hy],[x+hx,y+hy],[x+hx,y-hy]]}


class RightTurnLaneTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.geometry=self.root/'road_geometry.json'
        self.samples=self.root/'native_samples.jsonl'
        self.geometry.write_text(json.dumps({'native_map_sha256':'a'*64,
          'approach_road_id':1,'turn_connector_road_id':13,'right_turn_lane_id':-2,
          'right_turn_lane_native_y_bounds_m':[-7.0,-3.5],
          'intersection_native_xy_bounds_m':[-7,-7,7,7],
          'right_turn_lane_design_native_verified':False}))

    def write(self,y,lane,exit_forward=None):
        rows=[sample(100,.05,-20,y,1,lane,[1,0]),
              sample(101,.10,-12,y,1,lane,[1,0]),
              sample(102,.15,-3,-2,13,-2,[.7,-.714142842]),
              sample(103,.20,-5.25,-12,4,-2,exit_forward or [0,-1])]
        self.samples.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')

    def test_geometry_covers_both_routes_and_fallback_turn_entry(self):
        report=check();self.assertTrue(report['passed'])
        self.assertEqual(len(report['cases']),4)
        self.assertEqual(set(CASE_APPROACH_Y_M.values()),{-5.25,-1.75})
        self.assertNotEqual(route(-5.25),route(-5.25,-10))
        self.assertFalse(report['right_turn_lane_design_and_signage_native_verified'])

    def test_right_lane_and_inner_lane_have_distinct_measured_occupancy(self):
        self.write(-5.25,-2);right=measure(self.samples,self.geometry)
        self.assertTrue(right['full_body_in_right_turn_lane_approach_samples'])
        self.assertEqual(right['approach_lane_identity_fraction'],1)
        self.assertFalse(right['right_turn_lane_design_native_verified'])
        self.write(-1.75,-1);inner=measure(self.samples,self.geometry)
        self.assertFalse(inner['full_body_in_right_turn_lane_approach_samples'])
        self.assertEqual(inner['approach_lane_identity_fraction'],0)

    def test_missing_source_and_unobserved_turn_rejected(self):
        self.write(-5.25,-2)
        with self.assertRaisesRegex(ValueError,'Missing required source: road_geometry.json'):
            measure(self.samples,self.root/'absent/road_geometry.json')
        self.write(-5.25,-2,[1,0])
        with self.assertRaisesRegex(ValueError,'Observed right-turn heading change missing'):
            measure(self.samples,self.geometry)

    def test_invented_lane_survey_rejected(self):
        self.write(-5.25,-2)
        context=json.loads(self.geometry.read_text());context['right_turn_lane_id']=-1
        self.geometry.write_text(json.dumps(context))
        with self.assertRaisesRegex(ValueError,'Right-turn-lane Native survey missing'):
            measure(self.samples,self.geometry)


if __name__=='__main__':unittest.main()
