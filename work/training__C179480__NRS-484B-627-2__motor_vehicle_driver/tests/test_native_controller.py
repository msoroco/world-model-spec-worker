import importlib.util
from pathlib import Path
import sys
import types
import unittest


path = Path(__file__).resolve().parents[1] / 'native_controller.py'
spec = importlib.util.spec_from_file_location('c179480_native_controller', path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FakeBlueprint:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class FakeLibrary:
    def __init__(self):
        self.blueprints = []

    def find(self, name):
        assert name == 'sensor.camera.rgb'
        item = FakeBlueprint()
        self.blueprints.append(item)
        return item


class FakeSensor:
    def __init__(self):
        self.callback = None
        self.destroyed = False

    def listen(self, callback):
        self.callback = callback

    def destroy(self):
        self.destroyed = True


class FakeWorld:
    def __init__(self, fail_at=None):
        self.sensors = []
        self.fail_at = fail_at

    def spawn_actor(self, blueprint, transform, attach_to):
        if len(self.sensors) == self.fail_at:
            raise RuntimeError('sensor spawn failed')
        sensor = FakeSensor()
        self.sensors.append(sensor)
        return sensor


class NativeControllerTest(unittest.TestCase):
    def test_four_source_cameras_spawn_and_route_frames(self):
        library, world = FakeLibrary(), FakeWorld()
        carla = types.SimpleNamespace(Location=lambda **kw: kw,
                                      Rotation=lambda **kw: kw,
                                      Transform=lambda location, rotation: (location, rotation))
        frames = []
        parent = object()
        sensors = module.install_cameras(world, library, carla, parent,
                                         lambda name, frame: frames.append((name, frame)))
        self.assertEqual(len(sensors), 4)
        self.assertEqual([b.attributes['sensor_tick'] for b in library.blueprints],
                         ['0.05'] * 4)
        self.assertEqual([b.attributes['image_size_x'] for b in library.blueprints],
                         ['1920', '1280', '1280', '1280'])
        for index, sensor in enumerate(sensors):
            sensor.callback(index)
        self.assertEqual([name for name, _ in frames],
                         ['overview', 'approach', 'reference_corner', 'driver_reference'])

    def test_partial_camera_spawn_is_cleaned_up(self):
        world = FakeWorld(fail_at=2)
        carla = types.SimpleNamespace(Location=lambda **kw: kw,
                                      Rotation=lambda **kw: kw,
                                      Transform=lambda *args: args)
        with self.assertRaisesRegex(RuntimeError, 'sensor spawn failed'):
            module.install_cameras(world, FakeLibrary(), carla, object(),
                                   lambda *_: None)
        self.assertTrue(all(sensor.destroyed for sensor in world.sensors))

    def test_stop_controller_uses_measured_pose_and_velocity(self):
        class Vehicle:
            def __init__(self):
                self.location = types.SimpleNamespace(x=0.0, y=0.0)
                self.velocity = types.SimpleNamespace(x=3.0, y=0.0, z=0.0)
                self.control = None

            def get_transform(self):
                return types.SimpleNamespace(location=self.location,
                                             rotation=types.SimpleNamespace(yaw=0.0))

            def get_velocity(self):
                return self.velocity

            def apply_control(self, control):
                self.control = control

        vehicle = Vehicle()
        control_type = lambda **kw: types.SimpleNamespace(**kw)
        controller = module.StopControl(15.0, 0.0)
        far = module.apply_stop_control(vehicle, control_type, controller)
        self.assertGreater(vehicle.control.throttle, 0)
        self.assertEqual(far['speed_mps'], 3.0)
        vehicle.location.x = 14.7
        near = module.apply_stop_control(vehicle, control_type, controller)
        self.assertEqual(vehicle.control.brake, 1.0)
        self.assertTrue(near['command']['target_reached'])

    def test_contrast_steers_toward_shoulder_and_does_not_stall_short(self):
        controller = module.StopControl(15.0, 3.3)
        first = controller.decide(0.0, 0.0, 2.0, 0.0)
        self.assertGreater(first['steer'], 0.0)
        slow = controller.decide(13.5, 3.3, 0.0, 0.0)
        self.assertGreater(slow['throttle'], 0.0)
        self.assertFalse(slow['target_reached'])


if __name__ == '__main__':
    unittest.main()
