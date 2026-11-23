import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from yield_site import validate_authored_site, validate_native_site
from yield_controller import PREFIX, SUFFIXES, Stage, speed_control
from yield_construction import stage_case
from yield_capture_sources import observe_sight


class Map:
    name = 'OpenDriveMap'

    def get_waypoint(self, point, project_to_road=False):
        assert project_to_road is False
        inventory = {(-20, 1.8): (158208, -1, False),
                     (0, 1.8): (158210, -1, True),
                     (1.8, 20): (158212, -1, False),
                     (1.8, 0): (158213, -1, True),
                     (-1.8, -20): (158214, 1, False),
                     (-60, 1.8): (158208, -1, False),
                     (1.8, 45): (158212, -1, False),
                     (1.8, 4): (158213, -1, True)}
        road, lane, junction = inventory[(point.x, point.y)]
        return NS(road_id=road, lane_id=lane, is_junction=junction,
                  junction_id=158209 if junction else 0,
                  transform=NS(location=point))


class World:
    def __init__(self, fail_second=False):
        self.map = Map()
        self.spawned = []
        self.fail_second = fail_second

    def get_map(self):
        return self.map

    def get_actors(self):
        sign = NS(id=301, trigger_volume=NS(contains=lambda point, transform:
                  (point.x, point.y) == (-20, 1.8)),
                  get_transform=lambda: object())
        return NS(filter=lambda pattern: [sign])

    def get_blueprint_library(self):
        return NS(find=lambda name: name)

    def try_spawn_actor(self, blueprint, transform):
        if self.fail_second and self.spawned:
            return None
        actor = NS(id=len(self.spawned) + 1, type_id=blueprint,
                   get_location=lambda: transform.location, destroyed=False)
        actor.destroy = lambda: setattr(actor, 'destroyed', True)
        self.spawned.append(actor)
        return actor


class ConstructionSourcesTests(unittest.TestCase):
    @staticmethod
    def location(**values):
        return NS(**values)

    def test_site_and_all_five_exact_stagings(self):
        site = validate_authored_site()
        self.assertEqual(site['through_road_ids'], [158212, 158213, 158214])
        self.assertFalse(site['native_marking_absence_claimed'])
        self.assertEqual(validate_native_site(World(), location_factory=self.location)
                         ['native_yield_sign_id'], 301)
        for suffix in SUFFIXES:
            with self.subTest(suffix=suffix):
                world = World()
                with stage_case(world, PREFIX + suffix,
                                location_factory=self.location) as staged:
                    self.assertEqual(len(world.spawned), 2)
                    self.assertNotEqual(staged['ego'].id, staged['through'].id)
                    self.assertEqual(staged['through_spawn_point_xy_m'],
                                     (1.8, 4.0) if suffix == 'yield_nearest_through_occupied'
                                     else (1.8, 45.0))
                self.assertTrue(all(actor.destroyed for actor in world.spawned))

    def test_failed_second_spawn_cleans_up(self):
        world = World(fail_second=True)
        with self.assertRaisesRegex(ValueError, 'could not spawn'):
            with stage_case(world, PREFIX + SUFFIXES[0],
                            location_factory=self.location):
                pass
        self.assertTrue(world.spawned[0].destroyed)

    def test_response_branches_and_invalid_inputs(self):
        targets = [Stage(PREFIX + suffix).target(10, within_intersection=False,
                                                through_vehicle_clear=False)
                   for suffix in SUFFIXES]
        self.assertEqual(targets, [2, 0, 8, 2, 2])
        self.assertGreater(speed_control(0, 4)['brake'], 0)
        with self.assertRaisesRegex(ValueError, 'Unknown exact'):
            Stage(PREFIX + 'wrong')

    def test_current_frame_sight_source(self):
        class Point:
            def __init__(self, x=0, y=0, z=0):
                self.x, self.y, self.z = x, y, z

            def distance(self, other):
                return ((self.x-other.x)**2 + (self.y-other.y)**2
                        + (self.z-other.z)**2)**.5

        class Transform:
            location = Point(-20, 1.8, .25)

            def transform(self, point):
                return Point(self.location.x+point.x, self.location.y+point.y,
                             self.location.z+point.z)

        actor = NS(id=1, get_transform=lambda: Transform(),
                   bounding_box=NS(contains=lambda point, transform: False))
        world = NS(get_snapshot=lambda: NS(frame=100), get_map=lambda: Map(),
                   cast_ray=lambda eye, target: [])
        through = NS(id=2)
        ray, sample = observe_sight(world, actor, through, 100, 5.0,
                                    location_factory=Point,
                                    visible_relation=lambda *args:
                                    {'a': 1, 'b': 2, 'visible': True})
        self.assertEqual(ray['target_road_id'], 158213)
        self.assertEqual(sample['visible_through_vehicle_ids'], [2])
        with self.assertRaisesRegex(ValueError, 'current Native frame'):
            observe_sight(world, actor, through, 99, 5.0,
                          location_factory=Point)


if __name__ == '__main__':
    unittest.main()
