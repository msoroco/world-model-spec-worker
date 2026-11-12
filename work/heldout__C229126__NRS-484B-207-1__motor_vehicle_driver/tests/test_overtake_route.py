from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overtake_route import case_target, choose_target, select_overtake_route, steer_speed_control


def lanes(direction=1, same_direction=True, steps=75):
    right, left = [], []
    for index in range(steps):
        for lane, lane_id, lateral, heading in (
                (right, 1, 0, direction),
                (left, 2, 3.5 * direction, direction if same_direction else -direction)):
            location = NS(x=index * 2.5 * direction, y=lateral)
            transform = NS(location=location,
                           get_forward_vector=lambda heading=heading: NS(x=heading, y=0))
            lane.append(NS(road_id=9, lane_id=lane_id, is_junction=False,
                           transform=transform))
    for chain in (right, left):
        for i, point in enumerate(chain):
            point.next = lambda step, chain=chain, i=i: [chain[i + 1]] if i + 1 < len(chain) else []
    right[0].get_left_lane = lambda: left[0]
    world_map = NS(get_spawn_points=lambda: [NS(location=right[0].transform.location)],
                   get_waypoint=lambda _: right[0])
    return world_map, right, left


class OvertakeRouteTests(unittest.TestCase):
    def test_same_direction_left_pair_in_both_approaches(self):
        for direction in (1, -1):
            world_map, right, left = lanes(direction)
            route = select_overtake_route(world_map)
            self.assertIs(route['right'][0], right[0])
            self.assertIs(route['left'][0], left[0])
            self.assertEqual(len(route['left']), 71)
        world_map, _, _ = lanes(same_direction=False)
        with self.assertRaisesRegex(ValueError, 'No connected'):
            select_overtake_route(world_map)

    def test_return_requires_measured_body_clearance(self):
        world_map, _, _ = lanes()
        route = select_overtake_route(world_map)
        before = choose_target(route, [10, 0], 18, 17, requested_return_clearance_m=3)
        premature = choose_target(route, [10, 0], 20, 17,
                                  requested_return_clearance_m=3)
        after = choose_target(route, [10, 0], 20, 17, passed_abreast=True,
                              requested_return_clearance_m=3)
        self.assertEqual(before['phase'], 'pass_left')
        self.assertEqual(premature['phase'], 'pass_left')
        self.assertEqual(after['phase'], 'return_right')
        self.assertEqual(before['waypoint'].lane_id, 2)
        self.assertEqual(after['waypoint'].lane_id, 1)

    def test_feedback_control_both_directions(self):
        east = steer_speed_control([0, 0], [1, 0], [2, 0], [5, 1])
        west = steer_speed_control([0, 0], [-1, 0], [-2, 0], [-5, -1])
        self.assertGreater(east['steer'], 0)
        self.assertGreater(west['steer'], 0)
        self.assertGreater(east['throttle'], 0)
        fast = steer_speed_control([0, 0], [1, 0], [12, 0], [5, 0])
        self.assertEqual(fast['throttle'], 0)
        self.assertGreater(fast['brake'], 0)

    def test_exact_lateral_and_signed_return_targets(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                world_map, _, _ = lanes(direction)
                route = select_overtake_route(world_map)
                row = {
                    'road_tangent_xy': [direction, 0],
                    'ego_corners': [[0, 3.5 * direction], [2 * direction, 3.5 * direction],
                                    [2 * direction, 4.5 * direction], [0, 4.5 * direction]],
                    'other_corners': [[3 * direction, -.5 * direction],
                                      [5 * direction, -.5 * direction],
                                      [5 * direction, .5 * direction],
                                      [3 * direction, .5 * direction]],
                }
                wide = case_target(route, 'left_pass_wide', [0, 3.5 * direction],
                                   row, passed_abreast=False)
                narrow = case_target(route, 'left_pass_narrow', [0, 3.5 * direction],
                                     row, passed_abreast=False)
                self.assertEqual(wide['phase'], 'pass_left')
                self.assertAlmostEqual(abs(wide['target_xy'][1] - narrow['target_xy'][1]), 1)
                # Signed clearance permits the planned earlier return; the
                # same original body geometry keeps the later return in lane 2.
                row['ego_corners'] = [[4.8 * direction, 3.5 * direction],
                                      [6.8 * direction, 3.5 * direction],
                                      [6.8 * direction, 4.5 * direction],
                                      [4.8 * direction, 4.5 * direction]]
                early = case_target(route, 'return_before_clear', [5 * direction, 3.5 * direction],
                                    row, passed_abreast=True)
                late = case_target(route, 'return_after_clear', [5 * direction, 3.5 * direction],
                                   row, passed_abreast=True)
                self.assertEqual(early['phase'], 'return_right')
                self.assertEqual(late['phase'], 'pass_left')


if __name__ == '__main__':
    unittest.main()
