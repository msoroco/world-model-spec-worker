"""Check that the runner surveys the same lanes used by the authored route."""
import types
import math
import unittest

from geometry import CASE_PLACEMENTS, route
from engineering import parameters
from runner import map_survey, observed_speed_mps


class Direction:
    def __init__(self, x, y):
        self.x, self.y = x, y


class Waypoint:
    def __init__(self, road_id, vector):
        self.id = road_id
        self.road_id = road_id
        self.transform = types.SimpleNamespace(get_forward_vector=lambda: Direction(*vector))
        self.successors = []

    def next(self, step):
        self._step = step
        return self.successors


class Map:
    def __init__(self):
        self.queries = []
        self.lanes = {
            (-30, 1.75): Waypoint(1, (1, 0)),
            (-30, -1.75): Waypoint(1, (-1, 0)),
            (1.75, -30): Waypoint(4, (0, -1)),
            (-1.75, -30): Waypoint(4, (0, 1)),
        }
        self.lanes[(-30, 1.75)].successors = [self.lanes[(1.75, -30)]]

    def get_waypoint(self, location, *, project_to_road, lane_type):
        self.queries.append((location.x, location.y, project_to_road, lane_type))
        return self.lanes.get((location.x, location.y))


class RunnerSurveyTest(unittest.TestCase):
    def test_observed_speed_reads_current_native_velocity(self):
        actor = types.SimpleNamespace(get_velocity=lambda: types.SimpleNamespace(x=3.0, y=4.0, z=0.0))
        self.assertEqual(observed_speed_mps(actor), 5.0)
        actor.get_velocity = lambda: types.SimpleNamespace(x=0.0, y=0.0, z=0.0)
        self.assertEqual(observed_speed_mps(actor), 0.0)
        actor.get_velocity = lambda: types.SimpleNamespace(x=math.nan, y=0.0, z=0.0)
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            observed_speed_mps(actor)

    def test_survey_and_reflected_route_share_approach_and_southbound_exit(self):
        carla = types.SimpleNamespace(Location=lambda **kw: types.SimpleNamespace(**kw),
                                      LaneType=types.SimpleNamespace(Driving='driving'))
        mapping = Map()
        survey = map_survey(carla, mapping, 'a' * 64)
        self.assertTrue(survey['native_lane_link_readback']['connected_lane_link'])
        self.assertEqual(survey['approach_right_normal_native'], [0, 1])
        self.assertEqual(survey['destination_forward_native'], [0.0, -1.0])
        self.assertEqual(survey['destination_exit_point_native_m'], [0, -7])
        self.assertEqual([(x, y) for x, y, _, _ in mapping.queries],
                         [(-30, 1.75), (-30, -1.75), (1.75, -30), (-1.75, -30)])
        for lateral in CASE_PLACEMENTS.values():
            points = route(lateral)
            self.assertTrue(all(-7 < y < 0 for x, y in points if x <= -7))
            native = parameters('controlled_1' if lateral == CASE_PLACEMENTS['controlled_1'] else 'controlled_2', 'primary')['native_route_xy_m']
            self.assertEqual(native, [[x,-y] for x,y in points])
            self.assertTrue(all(0 < y < 7 for x,y in native if x <= -7))
            self.assertLess(native[-1][1], survey['destination_exit_point_native_m'][1])


if __name__ == '__main__':
    unittest.main()
