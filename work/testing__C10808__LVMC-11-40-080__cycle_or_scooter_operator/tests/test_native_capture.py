"""CPU checks of the Native route and pre-capture source boundary."""
import importlib.util
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('c10808_native_capture', ROOT/'native_capture.py')
native_capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native_capture)
from runner import load_scene, path_points


class Point:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Carla:
    Location = Point
    Rotation = Point

    class Transform:
        def __init__(self, location, rotation):
            self.location = location
            self.rotation = rotation


class Map:
    name = 'fixture-map'

    def get_spawn_points(self):
        return [Carla.Transform(Carla.Location(x=100., y=50., z=0.), Carla.Rotation(yaw=90.))]

    def get_waypoint(self, location):
        if location.y < 30.:
            return None
        return types.SimpleNamespace(road_id=7, lane_type='Driving',
                                     lane_width=3.5,
                                     transform=types.SimpleNamespace(location=location))


class NativeCaptureTests(unittest.TestCase):
    def test_rotated_route_stays_on_one_driving_road(self):
        scene = load_scene()
        origin, context = native_capture.discover_origin(Map(), scene, Carla)
        pose = native_capture.local_transform(Carla, origin, 2., 3.)
        self.assertAlmostEqual(pose.location.x, 97.)
        self.assertAlmostEqual(pose.location.y, 52.)
        self.assertEqual(context['road_id'], 7)
        self.assertGreater(context['waypoint_count'],
                           sum(map(len, path_points(scene).values())))
        self.assertEqual(context['maximum_map_support_spacing_m'], 1.0)
        self.assertEqual(context['alley_classification'], 'unresolved_requires_local_review')

    def test_missing_road_support_rejected(self):
        scene = load_scene()
        class BadMap(Map):
            def get_waypoint(self, location):
                return None
        with self.assertRaisesRegex(ValueError, 'lacks connected turn geometry'):
            native_capture.discover_origin(BadMap(), scene, Carla)

    def test_snapped_distant_road_rejected(self):
        class DistantMap(Map):
            def get_waypoint(self, location):
                waypoint = super().get_waypoint(location)
                if waypoint is not None:
                    waypoint.transform.location = Carla.Location(
                        x=location.x+10., y=location.y, z=location.z)
                return waypoint
        with self.assertRaisesRegex(ValueError, 'lacks connected turn geometry'):
            native_capture.discover_origin(DistantMap(), load_scene(), Carla)

    def test_capture_requires_sealable_source_and_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authorization = root/'authorization.txt'
            authorization.write_text('fixture authorization source; no actual authorization claim')
            with self.assertRaisesRegex(ValueError, 'construction.json'):
                native_capture.run_native(load_scene(), root, '127.0.0.1', 2000,
                                          authorization)
            (root/'construction.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'runner.py'):
                native_capture.run_native(load_scene(), root, '127.0.0.1', 2000,
                                          authorization)

    def test_camera_frame_join_and_cleanup(self):
        class Sensor:
            def __init__(self):
                self.callback = None
                self.stopped = self.destroyed = False
            def listen(self, callback):
                self.callback = callback
            def stop(self):
                self.stopped = True
            def destroy(self):
                self.destroyed = True
        class World:
            def __init__(self):
                self.sensors = []
            def get_blueprint_library(self):
                return types.SimpleNamespace(find=lambda name: types.SimpleNamespace(
                    set_attribute=lambda key, value: None))
            def spawn_actor(self, blueprint, transform, attach_to):
                sensor = Sensor()
                self.sensors.append(sensor)
                return sensor
        class Pipe:
            def __init__(self):
                self.closed = False
                self.data = bytearray()
            def write(self, payload):
                self.data.extend(payload)
            def close(self):
                self.closed = True
        class Encoder:
            def __init__(self):
                self.stdin = Pipe()
            def wait(self, timeout):
                return 0
        world = World()
        encoders = []
        def spawn_encoder(*args, **kwargs):
            encoder = Encoder()
            encoders.append(encoder)
            return encoder
        with tempfile.TemporaryDirectory() as directory, patch.object(
                native_capture.subprocess, 'Popen', side_effect=spawn_encoder):
            cameras = native_capture.Cameras(world, object(), Path(directory), Carla)
            self.assertEqual(len(world.sensors), 4)
            for sensor in world.sensors:
                sensor.callback(types.SimpleNamespace(frame=41, raw_data=b'frame'))
            cameras.append(41)
            self.assertTrue(all(e.stdin.data == b'frame' for e in encoders))
            for sensor in world.sensors:
                sensor.callback(types.SimpleNamespace(frame=42, raw_data=b'frame'))
            with self.assertRaisesRegex(ValueError, 'camera/frame mismatch'):
                cameras.append(43)
            cameras.close()
            self.assertTrue(all(s.stopped and s.destroyed for s in world.sensors))
            self.assertTrue(all(e.stdin.closed for e in encoders))

    def test_partial_camera_spawn_closes_prior_sensor(self):
        class Sensor:
            stopped = destroyed = False
            def listen(self, callback):
                pass
            def stop(self):
                self.stopped = True
            def destroy(self):
                self.destroyed = True
        sensor = Sensor()
        class World:
            calls = 0
            def get_blueprint_library(self):
                return types.SimpleNamespace(find=lambda name: types.SimpleNamespace(
                    set_attribute=lambda key, value: None))
            def spawn_actor(self, blueprint, transform, attach_to):
                self.calls += 1
                return sensor if self.calls == 1 else None
        class Encoder:
            stdin = types.SimpleNamespace(closed=False, close=lambda: None)
            def wait(self, timeout):
                return 0
        with tempfile.TemporaryDirectory() as directory, patch.object(
                native_capture.subprocess, 'Popen', return_value=Encoder()):
            with self.assertRaisesRegex(ValueError, 'camera spawn failed'):
                native_capture.Cameras(World(), object(), Path(directory), Carla)
        self.assertTrue(sensor.stopped and sensor.destroyed)


if __name__ == '__main__':
    unittest.main()
