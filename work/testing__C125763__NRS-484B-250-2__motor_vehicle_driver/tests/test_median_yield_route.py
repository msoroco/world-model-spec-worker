import importlib.util
import unittest
from pathlib import Path

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('median_yield_route',root/'median_yield_route.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)


def scene():
    return {'same_statutory_crossing':True,
            'crossing_polygon_xy_m':[[10,-3],[20,-3],[20,3],[10,3]],
            'approach_relation':'different_highways',
            'yield_sign':{'native_id':17,'governed_lane_id':1},
            'ego_yield_line_xy_m':[8,0],
            'approaches':{
                'ego':{'highway_id':'EW','lane_id':1,'forward_xy':[1,0],
                       'route_xy_m':[[0,0],[15,0],[30,0]]},
                'other':{'highway_id':'NS','lane_id':1,'forward_xy':[0,1],
                         'route_xy_m':[[15,-15],[15,0],[15,15]]}}}


class YieldRouteTests(unittest.TestCase):
    def test_two_routes_and_different_highways(self):
        self.assertIs(mod.validate_scene(scene())['same_statutory_crossing'],True)
        bad=scene();bad['approaches']['other']['highway_id']='EW'
        with self.assertRaisesRegex(ValueError,'one highway'):mod.validate_scene(bad)
        bad=scene();bad['approaches']['other']['route_xy_m']=[[0,12],[15,12],[30,12]]
        with self.assertRaisesRegex(ValueError,'other route'):mod.validate_scene(bad)

    def test_yield_line_and_governed_ego_approach(self):
        bad=scene();bad['yield_sign']['governed_lane_id']=2
        with self.assertRaisesRegex(ValueError,'govern ego'):mod.validate_scene(bad)
        bad=scene();bad['ego_yield_line_xy_m']=[15,0]
        with self.assertRaisesRegex(ValueError,'Yield line'):mod.validate_scene(bad)

    def test_opposite_left_turn_contract(self):
        opposite=scene();opposite['approach_relation']='opposite_directions'
        opposite['other_left_turn_intended']=True
        opposite['approaches']['other'].update({'highway_id':'EW','forward_xy':[-1,0],
            'route_xy_m':[[30,0],[15,0],[15,-15]]})
        mod.validate_scene(opposite)
        opposite['approaches']['other']['forward_xy']=[1,0]
        with self.assertRaisesRegex(ValueError,'opposing headings'):mod.validate_scene(opposite)

    def test_yield_brakes_for_conflict_and_releases_when_clear(self):
        self.assertEqual(mod.yield_control(2,4,False),(0.0,1.0))
        throttle,brake=mod.yield_control(2,0,True)
        self.assertGreater(throttle,0);self.assertEqual(brake,0)
        with self.assertRaisesRegex(ValueError,'uncleared conflict'):
            mod.yield_control(-1,4,False)

if __name__=='__main__':unittest.main()
