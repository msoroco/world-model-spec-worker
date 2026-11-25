import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("camera_rig", ROOT / "camera_rig.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
from freight_contract import SourceError


class Blueprint:
    def __init__(self):
        self.attributes = {}
    def set_attribute(self, key, value):
        self.attributes[key] = value


class Sensor:
    def __init__(self):
        self.callback = None
        self.stopped = False
        self.destroyed = False
    def listen(self, callback):
        self.callback = callback
    def stop(self):
        self.stopped = True
    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.sensors = []
    def try_spawn_actor(self, blueprint, transform):
        sensor = Sensor()
        self.sensors.append((blueprint.attributes.copy(), transform, sensor))
        return sensor


class Carla:
    @staticmethod
    def Location(**values):
        return values
    @staticmethod
    def Rotation(**values):
        return values
    @staticmethod
    def Transform(location, rotation):
        return (location, rotation)


class Adapter:
    def __init__(self):
        self.carla = Carla()
        self.world = World()
        self.owned = []
        self.blueprint = Blueprint()
    def _blueprint(self, identifier):
        assert identifier == "sensor.camera.rgb"
        return self.blueprint


class CameraRigTests(unittest.TestCase):
    def test_four_reviewed_poses_and_profile_are_spawned(self):
        adapter = Adapter()
        pose = {"x": 1, "y": 2, "z": 3, "pitch": -10, "yaw": 30, "roll": 0}
        site = {"camera_transforms": {name: pose for name in module.CAMERAS}}
        with module.CameraRig(adapter, site) as rig:
            self.assertEqual(len(adapter.world.sensors), 4)
            for name, (width, height) in module.CAMERAS.items():
                attributes, _, _ = adapter.world.sensors[list(module.CAMERAS).index(name)]
                self.assertEqual(attributes["image_size_x"], str(width))
                self.assertEqual(attributes["image_size_y"], str(height))
                self.assertEqual(attributes["sensor_tick"], "0.05")
                rig.queues[name].put((101, b"original bytes"))
                self.assertEqual(rig.read_camera(name, 101)[0], 101)
            with self.assertRaisesRegex(SourceError, "frame drift"):
                rig.queues["overview"].put((102, b"wrong frame"))
                rig.read_camera("overview", 103)
        self.assertTrue(all(sensor.stopped and sensor.destroyed for _, _, sensor in adapter.world.sensors))
        self.assertEqual(adapter.owned, [])

    def test_missing_camera_pose_rejected_before_spawn(self):
        adapter = Adapter()
        with self.assertRaisesRegex(SourceError, "four source-reviewed"):
            with module.CameraRig(adapter, {"camera_transforms": {}}):
                pass
        self.assertEqual(adapter.world.sensors, [])

    def test_partial_camera_spawn_cleans_owned_sensors(self):
        adapter = Adapter()
        original_spawn = adapter.world.try_spawn_actor
        def fail_third(blueprint, transform):
            if len(adapter.world.sensors) == 2:
                return None
            return original_spawn(blueprint, transform)
        adapter.world.try_spawn_actor = fail_third
        pose = {"x": 1, "y": 2, "z": 3, "pitch": -10, "yaw": 30, "roll": 0}
        site = {"camera_transforms": {name: pose for name in module.CAMERAS}}
        with self.assertRaisesRegex(SourceError, "camera spawn failed"):
            with module.CameraRig(adapter, site):
                pass
        self.assertTrue(all(sensor.stopped and sensor.destroyed
                            for _, _, sensor in adapter.world.sensors))
        self.assertEqual(adapter.owned, [])

    def test_cleanup_attempts_every_sensor_after_one_destroy_error(self):
        adapter = Adapter()
        pose = {"x": 1, "y": 2, "z": 3, "pitch": -10, "yaw": 30, "roll": 0}
        rig = module.CameraRig(adapter, {"camera_transforms":
                                         {name: pose for name in module.CAMERAS}})
        rig.__enter__()
        failing = adapter.world.sensors[-1][2]
        failing.destroy = lambda: (_ for _ in ()).throw(RuntimeError("sensor destroy failed"))
        with self.assertRaisesRegex(SourceError, "camera cleanup failed"):
            rig.__exit__(None, None, None)
        self.assertTrue(all(sensor.stopped for _, _, sensor in adapter.world.sensors))
        self.assertEqual(adapter.owned, [failing])
