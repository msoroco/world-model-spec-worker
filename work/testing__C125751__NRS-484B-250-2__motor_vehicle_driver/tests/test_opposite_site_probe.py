import unittest
import math
from types import SimpleNamespace

from opposite_site_probe import probe_native_opposite_approaches, route_pair_from_candidate
from opposite_turn_construction import check_routes


class Waypoint:
    def __init__(self, road, lane, x, y, yaw, junction=7, previous=None):
        self.road_id, self.lane_id = road, lane
        self.is_junction = junction is not None
        self.junction = junction
        self.transform = SimpleNamespace(
            location=SimpleNamespace(x=x, y=y),
            rotation=SimpleNamespace(yaw=yaw))
        self.predecessors = [] if previous is None else [previous]
        self.successors = []

    def previous(self, distance):
        return self.predecessors

    def next(self, distance):
        return self.successors

    def get_junction(self):
        return SimpleNamespace(id=self.junction)


class Map:
    name = 'FixtureTown'

    def __init__(self, waypoints):
        self.waypoints = waypoints

    def generate_waypoints(self, spacing):
        return self.waypoints


class World:
    def __init__(self, waypoints):
        self.native_map = Map(waypoints)

    def get_map(self):
        return self.native_map


def entry(road, lane, x, y, yaw, junction=7):
    approach = Waypoint(road, lane, x - 2 * math.cos(math.radians(yaw)),
                        y - 2 * math.sin(math.radians(yaw)), yaw, junction=None)
    return Waypoint(road, lane, x, y, yaw, junction, approach)


class OppositeSiteProbeTest(unittest.TestCase):
    def test_returns_same_junction_opposing_lane_candidate(self):
        world = World([entry(11, -1, -4, 0, 0),
                       entry(11, 1, 4, 0, 180),
                       entry(12, -1, 0, -4, 90)])
        candidates = probe_native_opposite_approaches(world)
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate['approach_road_lanes'], [[11, -1], [11, 1]])
        self.assertEqual(candidate['approach_angle_deg'], 180)
        self.assertEqual(candidate['review_status'], 'candidate_only')
        self.assertEqual(candidate['left_turn_exit_candidates'], [[], []])
        self.assertEqual(candidate['straight_exit_candidates'], [[], []])
        self.assertIn('source-reviewed route, exit and turn feasibility', candidate['unresolved'])

    def test_traces_left_exit_and_excludes_right_straight_and_other_junction(self):
        first = entry(11, -1, -4, 0, 0)
        second = entry(11, 1, 4, 0, 180)
        middle = Waypoint(30, -1, -2, 1, 45)
        left = Waypoint(31, -1, 0, 3, 90, junction=None)
        right = Waypoint(32, -1, 0, -3, -90, junction=None)
        straight = Waypoint(33, -1, 0, 0, 0, junction=None)
        middle.successors = [left, right, straight]
        first.successors = [middle]
        other_left = Waypoint(34, -1, 1, -3, -90, junction=None)
        second.successors = [other_left]
        candidate = probe_native_opposite_approaches(World([first, second]))[0]
        self.assertEqual(candidate['left_turn_exit_candidates'][0], [
            {'exit_road_lane': [31, -1], 'exit_xy_yaw': [0, 3, 90],
             'turn_angle_deg': 90,
             'route_xy': [[-6.0, 0.0], [-4.0, 0.0], [-2.0, 1.0], [0, 3]]}])
        self.assertEqual(candidate['left_turn_exit_candidates'][1][0]['exit_road_lane'], [34, -1])
        self.assertEqual(candidate['straight_exit_candidates'][0][0]['exit_road_lane'], [33, -1])

    def test_rejects_distant_or_nonfinite_exit_and_terminates_cycle(self):
        first = entry(11, -1, -4, 0, 0)
        second = entry(11, 1, 4, 0, 180)
        cycle = Waypoint(30, -1, -2, 0, 20)
        first.successors = [cycle]
        cycle.successors = [cycle,
                            Waypoint(31, -1, 50, 0, 90, junction=None),
                            Waypoint(32, -1, 0, float('nan'), 90, junction=None)]
        foreign = Waypoint(40, -1, -1, 0, 45, junction=9)
        foreign.successors = [Waypoint(41, -1, 0, 3, 90, junction=None)]
        cycle.successors.append(foreign)
        candidate = probe_native_opposite_approaches(World([first, second]))[0]
        self.assertEqual(candidate['left_turn_exit_candidates'], [[], []])

    def test_native_route_pair_feeds_existing_two_vehicle_geometry_checker(self):
        first = entry(11, -1, -4, 0, 0)
        second = entry(11, 1, 4, 0, 180)
        left_middle = Waypoint(30, -1, 0, 0, 45)
        left_exit = Waypoint(31, -1, 0, 3, 90, junction=None)
        left_middle.successors = [left_exit]
        first.successors = [left_middle]
        straight_middle = Waypoint(40, -1, 2, 0, 180)
        straight_exit = Waypoint(41, -1, -1, 0, 180, junction=None)
        straight_middle.successors = [straight_exit]
        second.successors = [straight_middle]
        candidate = probe_native_opposite_approaches(World([first, second]))[0]
        site = route_pair_from_candidate(candidate, 'ego')
        self.assertEqual(site['expected_approach_lanes'],
                         {'ego': [11, -1], 'other': [11, 1]})
        self.assertEqual(site['review_status'], 'candidate_only')
        result = check_routes(site['routes'], 'ego')
        self.assertEqual(result['approach_separation_deg'], 180)
        self.assertEqual(result['routes']['ego']['deflection_deg'], 90)

    def test_route_pair_rejects_missing_straight_branch(self):
        first = entry(11, -1, -4, 0, 0)
        second = entry(11, 1, 4, 0, 180)
        first.successors = [Waypoint(31, -1, 0, 3, 90, junction=None)]
        candidate = probe_native_opposite_approaches(World([first, second]))[0]
        with self.assertRaisesRegex(ValueError, 'Both Native route branches'):
            route_pair_from_candidate(candidate, 'ego')
        with self.assertRaisesRegex(ValueError, 'Nonnegative route branch indices'):
            route_pair_from_candidate(candidate, 'ego', left_index=-1)

    def test_rejects_perpendicular_and_other_junction(self):
        world = World([entry(11, -1, -4, 0, 0),
                       entry(12, -1, 0, -4, 90),
                       entry(11, 1, 4, 0, 180, junction=9)])
        self.assertEqual(probe_native_opposite_approaches(world), [])

    def test_rejects_ambiguous_or_missing_upstream_lane(self):
        one = entry(11, -1, -4, 0, 0)
        one.predecessors.append(Waypoint(13, -1, -5, 0, 0, junction=None))
        world = World([one, entry(11, 1, 4, 0, 180)])
        self.assertEqual(probe_native_opposite_approaches(world), [])

    def test_rejects_nonfinite_sampling(self):
        with self.assertRaisesRegex(ValueError, 'Finite bounded'):
            probe_native_opposite_approaches(World([]), sample_m=float('nan'))


if __name__ == '__main__':
    unittest.main()
