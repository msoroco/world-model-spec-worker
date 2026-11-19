import json
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
import runner

class ExactConstruction(unittest.TestCase):
    def test_materialized_site_route_and_controller(self):
        root=Path(__file__).resolve().parents[1]
        config=runner.validate_config(json.loads((root/'config.json').read_text()))
        packet=json.loads((root/'site_packet.json').read_text())
        points=[NS(road_id=r,lane_id=l,lane_type='Driving') for r in (1,2,3) for l in (-1,1)]
        world=NS(get_map=lambda:NS(name='TownX',generate_waypoints=lambda spacing:points))
        prepared=runner.prepare_site(world,packet,root,config)
        self.assertEqual(prepared['centerline_kind'],'marked')
        self.assertGreater(prepared['destination_exit_clearance_m'],1)
        self.assertFalse(prepared['physical_completion_claimed'])
        follower=runner.RouteFollower(prepared['route_xy_m'],target_speed_mps=config['requested_speed_mps'])
        self.assertGreater(follower.step(prepared['route_xy_m'][0],[1,0],0)['throttle'],0)
        packet['centerline_kind']='imaginary'
        with self.assertRaisesRegex(ValueError,'centerline kind'):
            runner.prepare_site(world,packet,root,config)
