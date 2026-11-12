import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from yield_construction import stage_case

PREFIX = 'testing__C158190__NRS-484B-257-1__motor_vehicle_driver__'


class Map:
    name = 'OpenDriveMap'
    lanes = {(-20, -1.8): (158190, -1, False),
             (0, -1.8): (158192, -1, True),
             (1.8, -20): (158194, -1, False),
             (1.8, 0): (158195, -1, True),
             (-1.8, 20): (158196, 1, False),
             (-60, -1.8): (158190, -1, False),
             (1.8, -45): (158194, -1, False),
             (1.8, -4): (158195, -1, True)}

    def get_waypoint(self, point, project_to_road=False):
        assert project_to_road is False
        road, lane, junction = self.lanes[(point.x, point.y)]
        return NS(road_id=road, lane_id=lane, is_junction=junction,
                  transform=NS(location=point))


class Actors:
    def filter(self, name):
        assert name == 'traffic.yield*'
        return [NS(id=500, trigger_volume=NS(contains=lambda point, transform:
                                            (point.x, point.y) == (-20, -1.8)),
                   get_transform=lambda: object())]


class World:
    def __init__(self, fail_second=False):
        self.map = Map()
        self.spawned = []
        self.fail_second = fail_second

    def get_map(self):
        return self.map

    def get_actors(self):
        return Actors()

    def get_blueprint_library(self):
        return NS(find=lambda name: name)

    def try_spawn_actor(self, blueprint, transform):
        if self.fail_second and self.spawned:
            return None
        actor = NS(id=len(self.spawned) + 1, type_id=blueprint,
                   get_location=lambda: transform.location,
                   destroy=lambda: None)
        actor.destroy = lambda: setattr(actor, 'destroyed', True)
        actor.destroyed = False
        self.spawned.append(actor)
        return actor


class ConstructionTests(unittest.TestCase):
    @staticmethod
    def location(**values):
        return NS(**values)

    def test_approaching_entered_and_clear_roles_cleanup(self):
        for suffix, expected_road, expected_point in (
                ('yield_nearest_view_through_approaches', 158194, (1.8, -45)),
                ('yield_nearest_view_through_entered', 158195, (1.8, -4)),
                ('yield_nearest_view_clear', None, None)):
            with self.subTest(suffix=suffix):
                world = World()
                with stage_case(world, PREFIX + suffix, location_factory=self.location) as staged:
                    self.assertEqual(staged['ego'].id, 1)
                    self.assertEqual(staged['through_spawn_point_xy_m'], expected_point)
                    self.assertEqual(len(world.spawned), 1 if expected_road is None else 2)
                    if expected_road is not None:
                        self.assertEqual(world.map.get_waypoint(staged['through'].get_location()).road_id,
                                         expected_road)
                self.assertTrue(all(actor.destroyed for actor in world.spawned))

    def test_failure_destroys_owned_ego(self):
        world = World(fail_second=True)
        with self.assertRaisesRegex(ValueError, 'could not spawn'):
            with stage_case(world, PREFIX + 'yield_nearest_view_no_slow',
                            location_factory=self.location):
                pass
        self.assertEqual(len(world.spawned), 1)
        self.assertTrue(world.spawned[0].destroyed)


if __name__ == '__main__':
    unittest.main()
