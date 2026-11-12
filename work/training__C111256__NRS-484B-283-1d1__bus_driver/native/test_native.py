"""Offline source construction checks bundled with each exact candidate."""
import json
from pathlib import Path
import unittest

from cameras import camera_plan
from controller import EngineeringKnobs, PathController, WalkFrame, WalkYieldController
from engineering import parameters
from geometry import check as geometry_check, route, pedestrian_route
from runner import check as runner_check

HERE=Path(__file__).resolve().parents[1]

class NativeConstructionTest(unittest.TestCase):
    def setUp(self):
        self.config=json.loads((HERE/'config.json').read_text())

    def test_current_exact_identity_and_geometry(self):
        result=runner_check(self.config)
        self.assertEqual(result['camera_count'],4)
        self.assertFalse(result['carla_imported'])
        self.assertEqual(geometry_check()['routes_intersect_at_xy_m'],[1.75,-11.0])
        self.assertEqual(len(route()),801)
        self.assertEqual(len(pedestrian_route()),131)

    def test_source_camera_profile(self):
        names=[row['name'] for row in camera_plan(self.config['candidate_id'])]
        self.assertEqual(names,['overview','approach','reference_corner','driver_reference'])

    def test_policy_uses_case_and_source(self):
        case=self.config['case_suffix'];candidate=self.config['candidate_id']
        plan=parameters(case,candidate)
        path=PathController(route(),3.8,35,EngineeringKnobs(
            lookahead_base_m=plan['knobs']['route_tracking_lookahead_m']))
        controller=WalkYieldController(path,policy=plan['yield_policy'],
             hold_margin_m=plan['knobs']['crosswalk_hold_margin_m'])
        observation=WalkFrame(native_frame=100,signal_actor_id=620,pedestrian_actor_id=720,
            display='Walk',pedestrian_facing_signal=True,pedestrian_in_crosswalk=True,
            pedestrian_xy_m=(1.7,-11),bus_front_y_m=-14,
            provenance='synthetic_native_sample')
        output=controller.step(observation=observation,position_xy_m=(1.75,-18),
            yaw_rad=1.5707963268,speed_mps=3,dt_s=.05)
        self.assertEqual(output['hold_requested'],case!='contrast')
        self.assertFalse(output['physical_yield_observed'])
        self.assertFalse(output['legal_outcome_claimed'])

if __name__=='__main__':unittest.main()
