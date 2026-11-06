"""CPU mock checks for bounded Native lane-link traversal."""
import unittest

from native_route_link import survey, full_body_destination_exit


class Vector:
    def __init__(self, x, y):
        self.x, self.y = x, y


class Transform:
    def __init__(self, x, y):
        self.vector = Vector(x, y)

    def get_forward_vector(self):
        return self.vector


class Waypoint:
    def __init__(self, ident, road, direction):
        self.id, self.road_id = ident, road
        self.transform = Transform(*direction)
        self.successors = []

    def next(self, step):
        assert step == 1.0
        return self.successors


class LinkSurveyTests(unittest.TestCase):
    def test_connected_branch(self):
        approach = Waypoint(1, 1, (1, 0))
        wrong = Waypoint(2, 3, (1, 0))
        turn = Waypoint(3, 3, (0, -1))
        exit_lane = Waypoint(4, 4, (0, -1))
        approach.successors = [wrong, turn]
        turn.successors = [exit_lane]
        result = survey(approach)
        self.assertTrue(result['connected_lane_link'])
        self.assertEqual(result['visited_waypoints'], 4)

    def test_disconnected_and_cycle(self):
        start = Waypoint(10, 1, (1, 0))
        loop = Waypoint(11, 3, (0, -1))
        start.successors = [loop]
        loop.successors = [start]
        result = survey(start)
        self.assertFalse(result['connected_lane_link'])
        self.assertEqual(result['visited_waypoints'], 2)

    def test_wrong_direction_does_not_pass(self):
        start = Waypoint(20, 1, (1, 0))
        opposing = Waypoint(21, 4, (0, 1))
        start.successors = [opposing]
        self.assertFalse(survey(start)['connected_lane_link'])

    def test_saved_full_body_exit_requires_all_vertices_and_heading(self):
        geometry = {'destination_exit_point_native_m': [0, -7],
                    'destination_forward_native': [0, -1]}
        body = [[0,-8],[1,-8],[1,-9],[0,-9]]
        row = {'native_body_xy_m': body, 'native_forward_xy': [0,-1]}
        self.assertTrue(full_body_destination_exit([row], geometry))
        self.assertFalse(full_body_destination_exit([
            {**row, 'native_body_xy_m': [[0,-6],*body[1:]]}], geometry))
        self.assertFalse(full_body_destination_exit([
            {**row, 'native_forward_xy': [1,0]}], geometry))


if __name__ == '__main__':
    unittest.main()
