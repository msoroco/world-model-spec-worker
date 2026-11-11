import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_pair import construct_pair, plan_pair


def transform(x, y, yaw):
    return NS(location=NS(x=x, y=y), rotation=NS(yaw=yaw))


class Map:
    name = 'TownFixture'
    def get_waypoint(self, location, project_to_road=False):
        if project_to_road:
            raise AssertionError('Native waypoint projection was enabled')
        if location.x < -5:
            return NS(is_junction=False, road_id=11, lane_id=-1,
                      lane_type='Driving')
        if abs(location.y) > 5:
            return NS(is_junction=False, road_id=22, lane_id=-1,
                      lane_type='Driving')
        return NS(is_junction=True, road_id=33, lane_id=-1,
                  lane_type='Driving', get_junction=lambda: NS(id=7))


SITE = {'native_map_name': 'TownFixture', 'crossing_id': 7,
        'ego_highway_id': 1, 'other_highway_id': 2,
        'polygon_source': 'synthetic polygon',
        'approach_geometry_source': 'synthetic waypoints',
        'crossing_polygon_xy_m': [[-5,-5],[5,-5],[5,5],[-5,5]]}


class NativePairTests(unittest.TestCase):
    def setUp(self):
        self.transforms = {'ego_approach': transform(-10, 0, 0),
                           'ego_entry': transform(-4, 0, 0),
                           'other_approach': transform(0, -10, 90),
                           'other_entry': transform(0, -4, 90)}

    def test_other_from_right_native_waypoints_and_cleanup(self):
        plan = plan_pair(Map(), SITE, self.transforms)
        self.assertGreater(plan['other_lateral_to_ego_right_m'], 0)
        self.assertLess(plan['ego_lateral_to_other_right_m'], 0)
        self.assertEqual(plan['native_junction_id'], 7)
        calls = []
        other = NS(destroy=lambda: calls.append('destroy'))
        world = NS(get_map=lambda: Map(),
                   try_spawn_actor=lambda blueprint, pose: other)
        with construct_pair(world, SITE, self.transforms, object()) as (_, spawned):
            self.assertIs(spawned, other)
        self.assertEqual(calls, ['destroy'])
        absent = NS(get_map=lambda: Map(), try_spawn_actor=lambda blueprint, pose: None)
        with self.assertRaisesRegex(ValueError, 'spawn failed'):
            with construct_pair(absent, SITE, self.transforms, object()):
                pass
        changed_map = NS(get_map=lambda: NS(name='OtherTown'),
                         try_spawn_actor=lambda blueprint, pose: other)
        with self.assertRaisesRegex(ValueError, 'Native map differs'):
            with construct_pair(changed_map, SITE, self.transforms, object()):
                pass

    def test_left_approach_and_wrong_junction_rejected(self):
        left = dict(self.transforms)
        left['other_approach'] = transform(0, 10, -90)
        left['other_entry'] = transform(0, 4, -90)
        with self.assertRaisesRegex(ValueError, 'not on ego right'):
            plan_pair(Map(), SITE, left)
        wrong = dict(SITE, crossing_id=8)
        with self.assertRaisesRegex(ValueError, 'not in selected junction'):
            plan_pair(Map(), wrong, self.transforms)
        away = dict(self.transforms)
        away['ego_approach'] = transform(-10, 0, 180)
        with self.assertRaisesRegex(ValueError, 'heading does not approach'):
            plan_pair(Map(), SITE, away)


if __name__ == '__main__':
    unittest.main()
