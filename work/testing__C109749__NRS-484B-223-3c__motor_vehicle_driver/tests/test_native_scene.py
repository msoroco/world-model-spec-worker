import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_scene import ASSIGNMENT, managed_world, run_managed_scene_capture, run_scene_capture, spawn_scene
from native_capture import CAMERA_DIMENSIONS, VIEWS
import test_native_capture as fixture
import test_carla_runner as runner_fixture


class Blueprint:
    def __init__(self, name):
        self.name = name
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class Actor:
    def __init__(self, identifier):
        self.id = identifier
        self.stopped = False
        self.destroyed = False

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, fail_spawn=None):
        self.spawned = []
        self.blueprints = []
        self.fail_spawn = fail_spawn

    def get_map(self):
        return SimpleNamespace(to_opendrive=lambda: 'reviewed-map')

    def get_settings(self):
        return SimpleNamespace(synchronous_mode=True, fixed_delta_seconds=.05)

    def get_blueprint_library(self):
        def find(name):
            blueprint = Blueprint(name)
            self.blueprints.append(blueprint)
            return blueprint
        return SimpleNamespace(find=find)

    def spawn_actor(self, blueprint, transform, attach_to=None):
        if len(self.spawned) == self.fail_spawn:
            return None
        actor = Actor(len(self.spawned) + 1)
        self.spawned.append(actor)
        return actor


class NativeSceneTests(unittest.TestCase):
    def setUp(self):
        Path('.runtime-work').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir='.runtime-work')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = ASSIGNMENT + '__below_50ft'
        self.site = fixture.site(self.root)
        map_path = self.root / self.site['native_map_source']['path']
        map_path.write_text(json.dumps({'opendrive_sha256': hashlib.sha256(
            b'reviewed-map').hexdigest()}) + '\n')
        self.site['native_map_source']['sha256'] = hashlib.sha256(map_path.read_bytes()).hexdigest()
        self.plan = {'case_id': self.case,
                     'vehicles': {role: {'blueprint_id': 'vehicle.diagnostic',
                                         'transform': {'x': 1}} for role in ('ego', 'receiving')},
                     'cameras': {view: {'blueprint_id': 'sensor.camera.rgb',
                                        'transform': {'z': 2}} for view in VIEWS},
                     'route_xy_m': [[0, 5], [0, 0], [5, -3]]}
        self.plan_path = self.root / 'spawn-plan.json'
        self._save_plan()
        self.world = World()

    def _save_plan(self):
        self.plan_path.write_text(json.dumps(self.plan) + '\n')
        self.binding = {'path': self.plan_path.name,
                        'sha256': hashlib.sha256(self.plan_path.read_bytes()).hexdigest()}

    def spawn(self):
        return spawn_scene(self.world, self.root, self.case, self.site,
                           self.binding, lambda spec: spec)

    def test_source_bound_vehicles_and_four_profile_cameras(self):
        scene, route = self.spawn()
        self.assertEqual(route, self.plan['route_xy_m'])
        self.assertEqual(set(scene.cameras), set(VIEWS))
        self.assertNotEqual(scene.ego.id, scene.receiving_vehicle.id)
        cameras = self.world.blueprints[2:]
        self.assertEqual(len(cameras), 4)
        for view, blueprint in zip(VIEWS, cameras):
            self.assertEqual(blueprint.attributes['image_size_x'], str(CAMERA_DIMENSIONS[view][0]))
            self.assertEqual(blueprint.attributes['image_size_y'], str(CAMERA_DIMENSIONS[view][1]))
            self.assertEqual(blueprint.attributes['sensor_tick'], '0.05')
        scene.close()
        scene.close()
        self.assertTrue(all(actor.destroyed for actor in self.world.spawned))
        self.assertTrue(all(camera.stopped for camera in scene.cameras.values()))

    def test_changed_source_or_map_rejected_before_spawn(self):
        self.plan_path.write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'source bytes differ'):
            self.spawn()
        self.assertEqual(self.world.spawned, [])
        self._save_plan()
        self.world.get_map = lambda: SimpleNamespace(to_opendrive=lambda: 'wrong-map')
        with self.assertRaisesRegex(ValueError, 'live OpenDRIVE differs'):
            self.spawn()
        self.assertEqual(self.world.spawned, [])

    def test_failed_camera_spawn_releases_both_vehicles_and_prior_sensors(self):
        self.world.fail_spawn = 3
        with self.assertRaisesRegex(ValueError, 'camera spawn failed'):
            self.spawn()
        self.assertEqual(len(self.world.spawned), 3)
        self.assertTrue(all(actor.destroyed for actor in self.world.spawned))
        self.assertTrue(self.world.spawned[-1].stopped)

    def test_failed_sensor_stop_does_not_skip_actor_destruction(self):
        scene, _ = self.spawn()
        def fail_stop():
            raise RuntimeError('sensor stop failed')
        next(iter(scene.cameras.values())).stop = fail_stop
        with self.assertRaisesRegex(RuntimeError, 'sensor stop failed'):
            scene.close()
        self.assertTrue(all(actor.destroyed for actor in self.world.spawned))
        scene.close()

    def test_spawn_failure_preserves_error_after_stop_failure(self):
        self.world.fail_spawn = 3
        original_spawn = self.world.spawn_actor
        def spawn(blueprint, transform, attach_to=None):
            actor = original_spawn(blueprint, transform, attach_to=attach_to)
            if actor is not None and len(self.world.spawned) == 3:
                actor.stop = lambda: (_ for _ in ()).throw(RuntimeError('cleanup stop failed'))
            return actor
        self.world.spawn_actor = spawn
        with self.assertRaisesRegex(ValueError, 'camera spawn failed'):
            self.spawn()
        self.assertTrue(all(actor.destroyed for actor in self.world.spawned))

    def test_wrong_case_or_missing_camera_plan_rejected(self):
        with self.assertRaisesRegex(ValueError, 'wrong exact'):
            spawn_scene(self.world, self.root, 'other__below_50ft', self.site,
                        self.binding, lambda spec: spec)
        self.plan['cameras'].pop('overview')
        self._save_plan()
        with self.assertRaisesRegex(ValueError, 'four-camera spawn plan'):
            self.spawn()
        self.assertEqual(self.world.spawned, [])

    def test_spawned_reader_capture_releases_all_original_actors(self):
        map_path = self.root / self.site['native_map_source']['path']
        map_path.write_text(json.dumps({'opendrive_sha256': hashlib.sha256(
            b'original-test-opendrive').hexdigest()}) + '\n')
        self.site['native_map_source']['sha256'] = hashlib.sha256(map_path.read_bytes()).hexdigest()
        self.plan['route_xy_m'] = [[0, 5], [0, 0], [5, 0], [5, -3]]
        self._save_plan()
        ego = runner_fixture.Actor(11, 5.0)
        other = runner_fixture.Actor(12, -3.0)
        sensors = {view: runner_fixture.Sensor() for view in VIEWS}
        world = runner_fixture.World(ego, other, sensors)
        actors = [ego, other, *sensors.values()]
        for actor in actors:
            actor.destroyed = False
            actor.destroy = lambda current=actor: setattr(current, 'destroyed', True)
        for index, sensor in enumerate(sensors.values(), start=13):
            sensor.id = index
        world.get_blueprint_library = self.world.get_blueprint_library
        spawned = iter(actors)
        world.spawn_actor = lambda blueprint, transform, attach_to=None: next(spawned)
        receipt = run_scene_capture(
            world=world, attempt_root=self.root, case_id=self.case,
            site=self.site, plan_binding=self.binding,
            transform_factory=lambda spec: spec,
            control_factory=lambda **values: SimpleNamespace(**values), count=4,
            dimensions={view: (2, 2) for view in VIEWS})
        self.assertEqual(receipt['capture_receipt']['delivered_measurement']['merge_observed'], True)
        self.assertFalse(receipt['physical_acceptance_claimed'])
        self.assertTrue(all(actor.destroyed for actor in actors))
        self.assertTrue(all(sensor.stopped for sensor in sensors.values()))

    def test_managed_world_restores_settings_and_weather_after_failure(self):
        class ManagedWorld:
            def __init__(self):
                self.settings = SimpleNamespace(synchronous_mode=False,
                                                fixed_delta_seconds=.1)
                self.weather = 'rain'
            def get_settings(self):
                return SimpleNamespace(**vars(self.settings))
            def apply_settings(self, settings):
                self.settings = SimpleNamespace(**vars(settings))
            def get_weather(self):
                return self.weather
            def set_weather(self, weather):
                self.weather = weather
        world = ManagedWorld()
        with self.assertRaisesRegex(RuntimeError, 'capture failed'):
            with managed_world(world):
                self.assertTrue(world.settings.synchronous_mode)
                self.assertEqual(world.settings.fixed_delta_seconds, .05)
                world.weather = 'clear'
                raise RuntimeError('capture failed')
        self.assertFalse(world.settings.synchronous_mode)
        self.assertEqual(world.settings.fixed_delta_seconds, .1)
        self.assertEqual(world.weather, 'rain')

    def test_managed_entrypoint_uses_world_lease(self):
        from unittest.mock import patch
        class ManagedWorld:
            def __init__(self):
                self.settings = SimpleNamespace(synchronous_mode=False,
                                                fixed_delta_seconds=.1)
                self.weather = 'rain'
            def get_settings(self):
                return SimpleNamespace(**vars(self.settings))
            def apply_settings(self, settings):
                self.settings = SimpleNamespace(**vars(settings))
            def get_weather(self):
                return self.weather
            def set_weather(self, weather):
                self.weather = weather
        world = ManagedWorld()
        with patch('native_scene.run_scene_capture') as capture:
            capture.side_effect = lambda **kw: (kw['world'].settings.synchronous_mode,
                                                kw['world'].settings.fixed_delta_seconds)
            self.assertEqual(run_managed_scene_capture(world=world), (True, .05))
        self.assertFalse(world.settings.synchronous_mode)


if __name__ == '__main__':
    unittest.main()
