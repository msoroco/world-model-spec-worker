import pathlib
import sys
import types
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from carla_cameras import OriginalCameras


class Blueprint:
    def __init__(self):
        self.attrs = {}
    def set_attribute(self, key, value):
        self.attrs[key] = value


class Sensor:
    def __init__(self, identity):
        self.id = identity
        self.callback = None
        self.destroyed = False
    def listen(self, callback):
        self.callback = callback
    def stop(self):
        pass
    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.sensors = []
        self.blueprints = []
    def get_blueprint_library(self):
        def find(name):
            if name != "sensor.camera.rgb":
                raise ValueError(name)
            bp = Blueprint()
            self.blueprints.append(bp)
            return bp
        return types.SimpleNamespace(find=find)
    def spawn_actor(self, bp, transform):
        sensor = Sensor(len(self.sensors) + 1)
        self.sensors.append(sensor)
        return sensor


class CameraTest(unittest.TestCase):
    def test_four_source_station_callbacks_and_frame_join(self):
        world = World()
        carla = types.SimpleNamespace(Location=lambda *args: args, Rotation=lambda *args: args,
                                      Transform=lambda *args: args)
        site = {name: {"xyz": [1.0, 2.0, 3.0], "rpy": [0.0, 0.0, 0.0], "source": "survey"}
                for name in ("front", "rear", "left", "right")}
        config = {"cameras": [{"name": name, "width": 2, "height": 2, "fov_deg": 90}
                              for name in ("front", "rear", "left", "right")]}
        cameras = OriginalCameras(world, carla, {"camera_transforms": site}, config)
        self.assertEqual(len(world.sensors), 4)
        self.assertTrue(all(bp.attrs["sensor_tick"] == "0.05" for bp in world.blueprints))
        self.assertTrue(all(bp.attrs["fov"] == "90" for bp in world.blueprints))
        image = types.SimpleNamespace(frame=12, width=2, height=2, raw_data=b"\x00\x00\xff\xff" * 4)
        for sensor in world.sensors:
            sensor.callback(image)
        source = cameras.read(12)
        self.assertEqual(set(source), set(site))
        self.assertTrue(all(value["bytes"].startswith(b"\x89PNG") for value in source.values()))
        cameras.close()
        self.assertTrue(all(sensor.destroyed for sensor in world.sensors))

    def test_missing_station_rejected(self):
        world = World()
        with self.assertRaisesRegex(ValueError, "four sourced camera station"):
            OriginalCameras(world, object(), {"camera_transforms": {}}, {"cameras": []})


if __name__ == "__main__":
    unittest.main()
