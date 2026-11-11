from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alley_route import control_step, select_alley_route


POLYGON = [[0, -3], [35, -3], [35, 3], [0, 3]]


def route(direction=1, lateral=0, lane_width=3):
    points = []
    for index in range(13):
        x = (2 if direction == 1 else 32) + index*2.5*direction
        location = NS(x=x, y=lateral)
        point = NS(road_id=17, lane_id=-direction, lane_width=lane_width,
                   is_junction=False,
                   transform=NS(location=location,
                                get_forward_vector=lambda direction=direction: NS(x=direction,y=0)))
        points.append(point)
    for index, point in enumerate(points):
        point.next = lambda step, index=index: [points[index+1]] if index+1 < len(points) else []
    return NS(get_spawn_points=lambda: [NS(location=points[0].transform.location)],
              get_waypoint=lambda _: points[0]), points


class AlleyRouteTests(unittest.TestCase):
    def test_east_and_west_sourced_polygon_routes(self):
        for direction, name in ((1, 'east'), (-1, 'west')):
            with self.subTest(direction=name):
                world_map, points = route(direction)
                selected = select_alley_route(world_map, POLYGON, direction=name,
                                              polygon_source='original road.xodr and Native map')
                self.assertEqual(selected, points)

    def test_rejects_outside_polygon_narrow_lane_and_wrong_direction(self):
        world_map, _ = route(lateral=3.2)
        with self.assertRaisesRegex(ValueError, 'No connected'):
            select_alley_route(world_map, POLYGON, direction='east', polygon_source='road.xodr')
        world_map, _ = route(lane_width=2)
        with self.assertRaisesRegex(ValueError, 'No connected'):
            select_alley_route(world_map, POLYGON, direction='east', polygon_source='road.xodr')
        world_map, _ = route(direction=-1)
        with self.assertRaisesRegex(ValueError, 'No connected'):
            select_alley_route(world_map, POLYGON, direction='east', polygon_source='road.xodr')
        with self.assertRaisesRegex(ValueError, 'source reference'):
            select_alley_route(world_map, POLYGON, direction='west', polygon_source='')

    def test_feedback_changes_speed_and_steer_without_legal_label(self):
        moving = control_step([0,0],[1,0],[1,0],[5,1],target_speed_mps=3)
        self.assertGreater(moving['steer'],0)
        self.assertGreater(moving['throttle'],0)
        fast = control_step([0,0],[1,0],[7,0],[5,0],target_speed_mps=3)
        self.assertEqual(fast['throttle'],0)
        self.assertGreater(fast['brake'],0)
        west = control_step([0,0],[-1,0],[-1,0],[-5,-1],target_speed_mps=3)
        self.assertGreater(west['steer'],0)
        with self.assertRaisesRegex(ValueError, 'too close'):
            control_step([0,0],[1,0],[1,0],[0,0],target_speed_mps=3)


if __name__ == '__main__':
    unittest.main()
