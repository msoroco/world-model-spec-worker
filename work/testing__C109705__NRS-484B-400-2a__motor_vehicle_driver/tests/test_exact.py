import json
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
import runner as construction
import finalizer

class ExactApproachConstruction(unittest.TestCase):
    def test_materialized_first_approach(self):
        root=Path(__file__).resolve().parents[1]
        self.assertTrue(construction.check_bundle(root)['cpu_check_passed'])
        with self.assertRaisesRegex(ValueError,'Missing required source'):
            finalizer.finalize(root,root/'analysis-report.json')
        packet=json.loads((root/'site_packet.json').read_text())
        points=[NS(road_id=r,lane_id=l,lane_type='Driving') for r in (1,2) for l in (-1,1)]
        world=NS(get_map=lambda:NS(name='TownX',generate_waypoints=lambda spacing:points))
        planned=construction.plan_left_turn(world,packet,root)
        self.assertFalse(planned['physical_completion_claimed'])
        self.assertEqual(len(construction.four_camera_plan(packet,planned['route_xy_m'])),4)
        follower=construction.RouteFollower(planned['route_xy_m'],target_speed_mps=3)
        self.assertGreater(follower.step(planned['route_xy_m'][0],[1,0],0)['throttle'],0)
        (root/'route_source.txt').write_text('altered')
        with self.assertRaisesRegex(ValueError,'Stale or missing'):
            construction.plan_left_turn(world,packet,root)
