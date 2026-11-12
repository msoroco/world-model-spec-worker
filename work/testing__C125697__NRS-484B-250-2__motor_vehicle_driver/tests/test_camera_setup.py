import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('c125697_camera_setup', ROOT / 'camera_setup.py')
camera = importlib.util.module_from_spec(spec)
spec.loader.exec_module(camera)


class Blueprint:
    def __init__(self):
        self.attributes = {}
    def set_attribute(self, name, value):
        self.attributes[name] = value


class Sensor:
    def __init__(self):
        self.stopped = self.destroyed = False
    def stop(self):
        self.stopped = True
    def destroy(self):
        self.destroyed = True


class CameraTests(unittest.TestCase):
    def test_four_profile_sources_attach_and_cleanup(self):
        created = []
        def spawn(blueprint, pose, **kwargs):
            sensor = Sensor()
            created.append((blueprint.attributes.copy(), pose, kwargs, sensor))
            return sensor
        world = NS(get_blueprint_library=lambda: NS(find=lambda name: Blueprint()),
                   spawn_actor=spawn)
        ego = object()
        transforms = {name: object() for name in camera.PROFILE}
        with camera.source_cameras(world, ego, transforms) as sensors:
            self.assertEqual(set(sensors), set(camera.PROFILE))
            for index, name in enumerate(camera.PROFILE):
                attributes, pose, kwargs, sensor = created[index]
                self.assertEqual(pose, transforms[name])
                self.assertEqual((attributes['image_size_x'], attributes['image_size_y']),
                                 tuple(map(str, camera.PROFILE[name])))
                self.assertEqual(attributes['sensor_tick'], '0.05')
                self.assertEqual(kwargs, {'attach_to': ego} if name == 'driver_reference' else {})
                self.assertFalse(sensor.destroyed)
        self.assertTrue(all(sensor.stopped and sensor.destroyed for *_, sensor in created))

    def test_partial_spawn_stops_created_sensors(self):
        created = []
        def spawn(blueprint, pose, **kwargs):
            if len(created) == 2:
                return None
            sensor = Sensor()
            created.append(sensor)
            return sensor
        world = NS(get_blueprint_library=lambda: NS(find=lambda name: Blueprint()),
                   spawn_actor=spawn)
        transforms = {name: object() for name in camera.PROFILE}
        with self.assertRaisesRegex(ValueError, 'Native camera spawn failed'):
            with camera.source_cameras(world, object(), transforms):
                pass
        self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in created))
        with self.assertRaisesRegex(ValueError, 'four named'):
            with camera.source_cameras(world, object(), {'overview': object()}):
                pass


if __name__ == '__main__':
    unittest.main()
