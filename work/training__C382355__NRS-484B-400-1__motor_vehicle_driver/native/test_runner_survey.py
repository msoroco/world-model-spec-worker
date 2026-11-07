"""CPU mock for CARLA's OpenDRIVE-to-Native Y reflection."""
import math
import types
import unittest

from engineering import parameters
from runner import map_survey, observed_speed_mps


class Waypoint:
    def __init__(self, road_id, lane_id, x, y, direction):
        self.road_id = road_id
        self.lane_id = lane_id
        self.lane_width = 3.5
        self.transform = types.SimpleNamespace(
            location=types.SimpleNamespace(x=x, y=y),
            get_forward_vector=lambda: types.SimpleNamespace(x=direction[0], y=direction[1]))


class Map:
    def __init__(self):
        self.queries = []
        self.lanes = {
            (-30, 5.25): Waypoint(1, -2, -30, 5.25, (1, 0)),
            (-30, 1.75): Waypoint(1, -1, -30, 1.75, (1, 0)),
            (-5.25, 30): Waypoint(4, -2, -5.25, 30, (0, 1)),
        }

    def get_waypoint(self, location, *, project_to_road, lane_type):
        self.queries.append((location.x, location.y, project_to_road, lane_type))
        return self.lanes.get((location.x, location.y))


class RunnerSurveyTest(unittest.TestCase):
    def test_speed_reads_current_native_velocity(self):
        actor = types.SimpleNamespace(get_velocity=lambda: types.SimpleNamespace(x=3., y=4., z=0.))
        self.assertEqual(observed_speed_mps(actor), 5.)
        actor.get_velocity = lambda: types.SimpleNamespace(x=0., y=0., z=2.)
        self.assertEqual(observed_speed_mps(actor), 2.)

    def test_nonfinite_observed_velocity_rejected(self):
        actor = types.SimpleNamespace(get_velocity=lambda: types.SimpleNamespace(x=math.nan, y=0., z=0.))
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            observed_speed_mps(actor)

    def test_reflected_route_and_native_lane_survey_agree(self):
        carla = types.SimpleNamespace(
            Location=lambda **kw: types.SimpleNamespace(**kw),
            LaneType=types.SimpleNamespace(Driving='driving'))
        mapping = Map()
        survey = map_survey(carla, mapping, 'a' * 64)
        self.assertEqual([(x, y) for x, y, _, _ in mapping.queries],
                         [(-30, 5.25), (-30, 1.75), (-5.25, 30)])
        self.assertEqual(survey['right_turn_lane_native_y_bounds_m'], [3.5, 7.0])
        self.assertEqual(survey['road_directions_native']['destination_lane'], [0.0, 1.0])
        for suffix in ('witness_1', 'witness_2'):
            for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
                plan = parameters(suffix, candidate)
                self.assertEqual(plan['native_route_xy_m'],
                                 [[x, -y] for x, y in plan['authored_route_xy_m']])
                self.assertEqual(plan['native_route_xy_m'][0][1],
                                 -plan['comparison_approach_y_m'])
                self.assertGreater(plan['native_route_xy_m'][-1][1], 7)


if __name__ == '__main__':
    unittest.main()
