import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lane_construction import control_step, route_targets, select_marked_one_way_pair


class Waypoint:
    def __init__(self, road, lane, x, y, reverse=False):
        self.road_id, self.lane_id = road, lane
        self.lane_type = "LaneType.Driving"
        self.is_junction = False
        self.left_lane_marking = NS(type="Solid")
        self.right_lane_marking = NS(type="Broken")
        self.transform = NS(location=NS(x=x, y=y))
        self.following = None
        self.adjacent = None

    def next(self, spacing):
        return [self.following] if self.following else []

    def get_left_lane(self):
        return self.adjacent

    def get_right_lane(self):
        return self.adjacent


def road(reverse=False, opposite=False):
    sign = -1 if reverse else 1
    main = [Waypoint(7, sign, i * (-2 if reverse else 2), 0) for i in range(5)]
    side = [Waypoint(7, 2 * sign, i * (-2 if reverse else 2), 3) for i in range(5)]
    for chain in (main, side):
        for a, b in zip(chain, chain[1:]):
            a.following = b
    for a, b in zip(main, side):
        a.adjacent = b
        b.adjacent = a
    starts = [main[0], side[0]]
    if opposite:
        starts.append(Waypoint(7, -sign, 0, -3))
    return NS(generate_waypoints=lambda spacing: starts), main, side


class NativeConstructionTests(unittest.TestCase):
    def test_three_exact_paths_in_both_directions(self):
        for reverse in (False, True):
            world_map, main, side = road(reverse)
            selected = select_marked_one_way_pair(world_map, steps=4)
            self.assertEqual(selected["lane_id"], main[0].lane_id)
            ordinary = route_targets(selected, "within_marked_lane")
            crossing = route_targets(selected, "unexcused_boundary_crossing")
            passing = route_targets(selected, "passing_boundary_crossing")
            self.assertEqual(ordinary["targets_xy_m"][0], crossing["targets_xy_m"][0])
            self.assertNotEqual(ordinary["targets_xy_m"][-1], crossing["targets_xy_m"][-1])
            self.assertEqual(crossing["targets_xy_m"], passing["targets_xy_m"])
            self.assertIsNone(crossing["overtaken_spawn"])
            self.assertIs(passing["overtaken_spawn"], main[2].transform)

    def test_opposite_direction_or_missing_marking_rejected(self):
        world_map, main, side = road(opposite=True)
        with self.assertRaisesRegex(ValueError, "No connected marked one-way"):
            select_marked_one_way_pair(world_map, steps=4)
        world_map, main, side = road()
        main[2].left_lane_marking = NS(type="LaneMarkingType.NONE")
        with self.assertRaisesRegex(ValueError, "No connected marked one-way"):
            select_marked_one_way_pair(world_map, steps=4)
        world_map, main, side = road()
        main[2].is_junction = True
        with self.assertRaisesRegex(ValueError, "No connected marked one-way"):
            select_marked_one_way_pair(world_map, steps=4)

    def test_passing_sweep_requests_distinct_connected_paths(self):
        world_map, _, _ = road()
        selected = select_marked_one_way_pair(world_map, steps=4)
        endings = []
        for index, fraction in enumerate((.4, .6, .8)):
            route = route_targets(selected, "passing_excursion-" + f"{index:04d}",
                                  crossing_fraction=fraction)
            self.assertIsNotNone(route["overtaken_spawn"])
            endings.append(route["targets_xy_m"][-1][1])
        self.assertEqual(endings, sorted(endings))
        self.assertEqual(len(set(endings)), 3)

    def test_controller_uses_readback_in_both_directions(self):
        east = control_step([0, 0], [1, 0], [2, 0], [5, 1])
        west = control_step([0, 0], [-1, 0], [-2, 0], [-5, -1])
        self.assertGreater(east["steer"], 0)
        self.assertGreater(west["steer"], 0)
        self.assertGreater(east["throttle"], 0)
        self.assertEqual(east["brake"], 0)
        fast = control_step([0, 0], [1, 0], [10, 0], [5, 0])
        self.assertEqual(fast["throttle"], 0)
        self.assertGreater(fast["brake"], 0)
        with self.assertRaisesRegex(ValueError, "undefined"):
            control_step([0, 0], [1, 0], [2, 0], [0, 0])


if __name__ == "__main__":
    unittest.main()
