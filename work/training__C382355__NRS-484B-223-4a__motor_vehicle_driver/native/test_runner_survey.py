"""CPU mock for both movements under CARLA's OpenDRIVE Y reflection."""
import types
import unittest

from engineering import parameters
from runner import map_survey


class Waypoint:
    def __init__(self, road_id, lane_id, x, y, forward):
        self.road_id = road_id
        self.lane_id = lane_id
        self.lane_width = 3.5
        self.transform = types.SimpleNamespace(
            location=types.SimpleNamespace(x=x, y=y),
            get_forward_vector=lambda: types.SimpleNamespace(x=forward[0], y=forward[1]))


class Map:
    def __init__(self):
        self.queries=[]
        self.lanes={
            (-30,5.25):Waypoint(1,-2,-30,5.25,(1,0)),
            (-5.25,30):Waypoint(4,-2,-5.25,30,(0,1)),
            (30,5.25):Waypoint(2,-2,30,5.25,(1,0)),
        }

    def get_waypoint(self, location, *, project_to_road, lane_type):
        self.queries.append((location.x,location.y,project_to_road,lane_type))
        return self.lanes.get((location.x,location.y))


class RunnerSurveyTest(unittest.TestCase):
    def test_both_native_exits_and_reflected_routes(self):
        carla=types.SimpleNamespace(
            Location=lambda **kw:types.SimpleNamespace(**kw),
            LaneType=types.SimpleNamespace(Driving='driving'))
        mapping=Map()
        survey=map_survey(carla,mapping,'a'*64)
        self.assertEqual([(x,y) for x,y,_,_ in mapping.queries],
                         [(-30,5.25),(-5.25,30),(30,5.25)])
        self.assertEqual(survey['right_only_lane_native_y_bounds_m'],[3.5,7.0])
        self.assertEqual(survey['road_directions_native']['right_turn_destination_lane'],[0.0,1.0])
        for suffix in ('controlled_1','controlled_2'):
            for candidate in ('primary','fallback1','fallback2','fallback3'):
                plan=parameters(suffix,candidate)
                self.assertEqual(plan['native_route_xy_m'],
                                 [[x,-y] for x,y in plan['authored_route_xy_m']])
                self.assertEqual(plan['native_route_xy_m'][0][1],5.25)
                if suffix=='controlled_1':
                    self.assertGreater(plan['native_route_xy_m'][-1][1],7)
                else:
                    self.assertGreater(plan['native_route_xy_m'][-1][0],7)


if __name__=='__main__':
    unittest.main()
