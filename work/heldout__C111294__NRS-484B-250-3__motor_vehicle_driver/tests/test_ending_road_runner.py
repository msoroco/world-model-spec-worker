from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ending_road_camera import CAMERAS
from ending_road_runner import (CASE, check_config, choose_control_targets,
                                conflict_polygon, control_to_waypoint, extend_exit)


def point(x, y, road=1, junction=False):
    p = NS(road_id=road, is_junction=junction,
           transform=NS(location=NS(x=x, y=y)))
    p.next = lambda step: []
    return p


def actor(x, y):
    state = NS(x=x, y=y)
    state.get_transform = lambda: NS(
        location=NS(x=state.x, y=state.y),
        get_forward_vector=lambda: NS(x=1., y=0.))
    state.get_velocity = lambda: NS(x=0., y=0.)
    state.bounding_box = NS(get_world_vertices=lambda _: [
        NS(x=state.x+dx, y=state.y+dy) for dx, dy in
        ((-.4,-.4),(.4,-.4),(.4,.4),(-.4,.4)) for _ in (0,1)])
    return state


class EndingRoadRunnerTests(unittest.TestCase):
    def test_config_four_capture_sources_and_identity(self):
        config = {'selected_case_id': CASE, 'law_id': 'NRS-484B-250-3',
                  'cell_id': 'C111294', 'actor': 'motor_vehicle_driver',
                  'rate_hz': 20, 'frames': 160, 'yield_clearance_m': 2,
                  'cameras': [{'name': name, 'width': size[0], 'height': size[1]}
                              for name, (_, _, size, _) in CAMERAS.items()]}
        check_config(config)
        config['cameras'][2]['height'] = 600
        with self.assertRaisesRegex(ValueError, 'cameras'):
            check_config(config)

    def test_connected_exit_and_intersection_geometry(self):
        approach, junction, exit_lane = point(0, -4), point(0, -2, 9, True), point(0, 0, 2)
        current = exit_lane
        for n in range(1, 13):
            successor = point(0, 2*n, 2)
            current.next = lambda step, successor=successor: [successor]
            current = successor
        path = extend_exit([approach, junction, exit_lane])
        self.assertEqual(len(path), 15)
        self.assertEqual(path[-1].transform.location.y, 24)
        zone = conflict_polygon([approach, junction, exit_lane],
                                [point(-4, 0, 3), point(-2, 0, 10, True), point(0, 0, 3)])
        self.assertEqual(zone, [[-5, -5], [3, -5], [3, 3], [-5, 3]])
        exit_lane.next = lambda step: []
        with self.assertRaisesRegex(ValueError, 'cannot be followed'):
            extend_exit([approach, junction, exit_lane])

    def test_yield_waits_for_through_passage_and_releases_once(self):
        subject, other = actor(0, -8), actor(-8, 0)
        routes = {'subject': [point(0, -8), point(0, 0)],
                  'other': [point(-8, 0), point(8, 0)],
                  'conflict_polygon_xy': [[-2,-2],[2,-2],[2,2],[-2,2]]}
        self.assertFalse(choose_control_targets(subject, other, routes, False, 2)[2])
        routes['other_seen_in_zone'] = True
        other.x = 1
        self.assertFalse(choose_control_targets(subject, other, routes, False, 2)[2])
        other.x = 6
        self.assertTrue(choose_control_targets(subject, other, routes, False, 2)[2])
        self.assertTrue(choose_control_targets(subject, other, routes, True, 2)[2])
        command = control_to_waypoint(other, point(10, 0), 5)
        self.assertGreater(command['throttle'], 0)
        self.assertEqual(command['steer'], 0)


if __name__ == '__main__':
    unittest.main()
