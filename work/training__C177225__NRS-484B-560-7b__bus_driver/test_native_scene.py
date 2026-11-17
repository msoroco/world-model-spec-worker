import unittest
from types import SimpleNamespace

from native_scene import SceneAssets, VIEWS, camera_plan, spawn_scene
from officer_direction import Crossing


class FakeLocation:
    def __init__(self, **values):
        self.__dict__.update(values)


class FakeRotation:
    def __init__(self, **values):
        self.__dict__.update(values)


class FakeTransform:
    def __init__(self, location, rotation):
        self.location = location
        self.rotation = rotation


class FakeBlueprint:
    def __init__(self, identifier):
        self.id = identifier
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class FakeLibrary:
    def __init__(self, identifiers):
        self.identifiers = set(identifiers)

    def find(self, identifier):
        if identifier not in self.identifiers:
            raise ValueError('Missing installed blueprint: ' + identifier)
        return FakeBlueprint(identifier)


class FakeActor:
    def __init__(self, blueprint, transform, attached_to):
        self.blueprint = blueprint
        self.transform = transform
        self.attached_to = attached_to
        self.bounding_box = SimpleNamespace(extent=SimpleNamespace(x=6.0))
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class FakeMap:
    def __init__(self, missing=False):
        self.missing = missing
        self.lookups = []

    def get_waypoint(self, location, **kwargs):
        self.lookups.append((location, kwargs))
        return None if self.missing else object()


class FakeWorld:
    def __init__(self, missing_lane=False, fail_at=None):
        self.library = FakeLibrary(('vehicle.mitsubishi.fusorosa',
                                    'walker.pedestrian.0001',
                                    'static.prop.test_rail', 'sensor.camera.rgb'))
        self.road_map = FakeMap(missing_lane)
        self.actors = []
        self.fail_at = fail_at

    def get_blueprint_library(self):
        return self.library

    def get_map(self):
        return self.road_map

    def spawn_actor(self, blueprint, transform, attach_to=None):
        if len(self.actors) == self.fail_at:
            raise RuntimeError('Native spawn failed')
        actor = FakeActor(blueprint, transform, attach_to)
        self.actors.append(actor)
        return actor


FAKE_CARLA = SimpleNamespace(Location=FakeLocation, Rotation=FakeRotation,
                             Transform=FakeTransform,
                             LaneType=SimpleNamespace(Driving='driving'))


class SceneConstructionTest(unittest.TestCase):
    def assets(self):
        return SceneAssets(rail_asset_blueprint='static.prop.test_rail')

    def test_spawns_real_actors_and_four_cameras_in_both_directions(self):
        for direction in (-1, 1):
            with self.subTest(direction=direction):
                world = FakeWorld()
                scene = spawn_scene(world, FAKE_CARLA, Crossing(), self.assets(),
                                    direction=direction)
                self.assertEqual(8, len(world.actors))
                self.assertEqual(set(VIEWS), set(scene['cameras']))
                self.assertEqual(2, len(scene['rails']))
                self.assertEqual(2, len(world.road_map.lookups))
                self.assertEqual('driving', world.road_map.lookups[0][1]['lane_type'])
                self.assertEqual(-70 * direction,
                                 scene['bus'].transform.location.x)
                self.assertEqual(-7 * direction,
                                 scene['requested_stop_x_m'])
                self.assertIs(scene['cameras']['driver_reference'].attached_to,
                              scene['bus'])
                self.assertTrue(all(actor.blueprint.id == 'sensor.camera.rgb'
                                    for actor in scene['cameras'].values()))
                self.assertFalse(scene['physical_success_claimed'])

    def test_approach_camera_moves_with_direction(self):
        for direction in (-1, 1):
            cameras = {item['name']: item for item in camera_plan(direction)}
            self.assertEqual(-42 * direction, cameras['approach']['xyz'][0])
            self.assertEqual(-18 * direction, cameras['overview']['xyz'][0])

    def test_missing_lane_or_rail_asset_rejected(self):
        world = FakeWorld(missing_lane=True)
        with self.assertRaisesRegex(ValueError, 'driving lane'):
            spawn_scene(world, FAKE_CARLA, Crossing(), self.assets(), direction=1)
        self.assertFalse(world.actors)
        with self.assertRaisesRegex(ValueError, 'rail crossing prop'):
            self.assets().__class__('vehicle.fake_rail').validate()
        with self.assertRaisesRegex(ValueError, 'Missing installed blueprint'):
            spawn_scene(FakeWorld(), FAKE_CARLA, Crossing(),
                        SceneAssets('static.prop.not_installed'), direction=1)

    def test_partial_native_spawn_is_cleaned_up(self):
        world = FakeWorld(fail_at=5)
        with self.assertRaisesRegex(RuntimeError, 'Native spawn failed'):
            spawn_scene(world, FAKE_CARLA, Crossing(), self.assets(), direction=1)
        self.assertEqual(5, len(world.actors))
        self.assertTrue(all(actor.destroyed for actor in world.actors))


if __name__ == '__main__':
    unittest.main()
