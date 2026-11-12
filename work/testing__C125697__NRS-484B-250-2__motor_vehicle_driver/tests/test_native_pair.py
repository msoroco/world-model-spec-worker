import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('native_pair', ROOT / 'native_pair.py')
pair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pair)
from controlled_pair import construct_off_pair


def at(x, y, yaw):
    return NS(location=NS(x=x, y=y), rotation=NS(yaw=yaw))


SITE = {'native_map_name': 'TownX', 'crossing_id': 44,
        'ego_highway_id': 'east-west', 'other_highway_id': 'north-south',
        'crossing_polygon_xy_m': [[10, -5], [20, -5], [20, 5], [10, 5]],
        'crossing_polygon_source': 'reviewed Native junction envelope',
        'approach_geometry_source': 'reviewed waypoints',
        'median_spacing_source': 'reviewed roadway opening',
        'all_entrances_source': 'reviewed affected-lane inventory',
        'same_statutory_crossing': True}


class Map:
    name = 'TownX'

    def get_waypoint(self, location, project_to_road=False):
        if project_to_road is not False:
            raise AssertionError('Native geometry must not project to another road')
        road = 2 if abs(location.y) > 6 else 3 if location.x > 25 else 1
        inside = 10 <= location.x <= 20 and -5 <= location.y <= 5
        return NS(road_id=road, lane_id=-1, lane_type='Driving',
                  is_junction=inside, get_junction=lambda: NS(id=44))


def transforms(side):
    other = {'right': (at(15, -12, 90), at(15, 0, 90)),
             'left': (at(15, 12, -90), at(15, 0, -90)),
             'opposite': (at(30, 0, 180), at(18, 0, 180))}[side]
    return {'ego_approach': at(0, 0, 0), 'ego_entry': at(12, 0, 0),
            'other_approach': other[0], 'other_entry': other[1]}


class PairTests(unittest.TestCase):
    def test_three_declared_approach_modes(self):
        for side in ('right', 'left', 'opposite'):
            with self.subTest(side=side):
                result = pair.plan_pair(Map(), SITE, transforms(side), side)
                self.assertEqual(result['declared_approach_side'], side)
                self.assertNotEqual(result['approaches']['ego']['road_id'],
                                    result['approaches']['other']['road_id'])
                self.assertFalse(result['physical_acceptance_claimed'])
        with self.assertRaisesRegex(ValueError, 'reciprocally'):
            pair.plan_pair(Map(), SITE, transforms('left'), 'right')

    def test_crossing_identity_and_facing_rejected(self):
        altered = dict(SITE, same_statutory_crossing=False)
        with self.assertRaisesRegex(ValueError, 'statutory median crossing'):
            pair.plan_pair(Map(), altered, transforms('right'), 'right')
        path = transforms('right')
        path['other_approach'] = at(15, -12, -90)
        with self.assertRaisesRegex(ValueError, 'heading does not approach'):
            pair.plan_pair(Map(), SITE, path, 'right')
        path = transforms('opposite')
        path['other_approach'] = at(30, 0, 0)
        with self.assertRaisesRegex(ValueError, 'heading does not approach'):
            pair.plan_pair(Map(), SITE, path, 'opposite')

    def test_spawn_failure_cleanup_and_map_guard(self):
        class Other:
            destroyed = False
            def destroy(self):
                self.destroyed = True
        other = Other()
        world = NS(get_map=lambda: Map(), try_spawn_actor=lambda blueprint, location: other)
        with pair.construct_pair(world, SITE, transforms('right'), object(), 'right') as (plan, actor):
            self.assertIs(actor, other)
            self.assertEqual(plan['native_junction_id'], 44)
        self.assertTrue(other.destroyed)
        failing = NS(get_map=lambda: Map(), try_spawn_actor=lambda blueprint, location: None)
        with self.assertRaisesRegex(ValueError, 'spawn failed'):
            with pair.construct_pair(failing, SITE, transforms('right'), object(), 'right'):
                pass
        wrong_map = NS(get_map=lambda: NS(name='TownY'),
                       try_spawn_actor=lambda blueprint, location: other)
        with self.assertRaisesRegex(ValueError, 'Native map differs'):
            with pair.construct_pair(wrong_map, SITE, transforms('right'), object(), 'right'):
                pass

    def test_off_state_wraps_other_actor_lifetime_and_restores(self):
        class Light:
            def __init__(self, identifier, road):
                self.id, self.road, self.state, self.frozen = identifier, road, 'Green', False
            def get_affected_lane_waypoints(self):
                return [NS(road_id=self.road, lane_id=-1)]
            def get_state(self):
                return self.state
            def set_state(self, value):
                self.state = value
            def freeze(self, value):
                self.frozen = value
        class Actors(list):
            def filter(self, pattern):
                return self
        class Other:
            destroyed = False
            def destroy(self):
                self.destroyed = True
        lights = [Light(17, 1), Light(18, 2)]
        other = Other()
        world = NS(get_map=lambda: Map(), get_actors=lambda: Actors(lights),
                   try_spawn_actor=lambda blueprint, location: other, tick=lambda: None)
        site = dict(SITE, entrance_road_lanes=[[1, -1], [2, -1]])
        with construct_off_pair(world, site, transforms('right'), object(), NS(Off='Off'), 'right') as (plan, actor, selected):
            self.assertIs(actor, other)
            self.assertEqual(selected, lights)
            self.assertEqual([light.state for light in lights], ['Off', 'Off'])
            self.assertFalse(other.destroyed)
        self.assertTrue(other.destroyed)
        self.assertEqual([light.state for light in lights], ['Green', 'Green'])
        self.assertFalse(any(light.frozen for light in lights))
        with self.assertRaisesRegex(ValueError, 'omitted from signal inventory'):
            with construct_off_pair(world, dict(site, entrance_road_lanes=[[1, -1], [3, -1]]),
                                    transforms('right'), object(), NS(Off='Off'), 'right'):
                pass


if __name__ == '__main__':
    unittest.main()
