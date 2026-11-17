import unittest
from types import SimpleNamespace

from opposite_site_probe import probe_native_opposite_approaches


class Waypoint:
    def __init__(self, road, lane, x, y, yaw, junction=7, previous=None):
        self.road_id, self.lane_id = road, lane
        self.is_junction = junction is not None
        self.junction = junction
        self.transform = SimpleNamespace(
            location=SimpleNamespace(x=x, y=y),
            rotation=SimpleNamespace(yaw=yaw))
        self.predecessors = [] if previous is None else [previous]

    def previous(self, distance):
        return self.predecessors

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
    approach = Waypoint(road, lane, x, y, yaw, junction=None)
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
        self.assertIn('source-reviewed routes and left-turn exit', candidate['unresolved'])

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
