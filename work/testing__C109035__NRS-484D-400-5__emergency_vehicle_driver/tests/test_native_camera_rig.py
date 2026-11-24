"""Fake Native sensor proof for the reviewed four-view bridge."""
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_camera_rig import NativeCameraRig


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


class Blueprint:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, name, value):
        self.attributes[name] = value


class World:
    def __init__(self):
        self.sensors = []
        self.blueprints = []
        self.spawns = []

    def get_settings(self):
        return SimpleNamespace(synchronous_mode=True,
                               no_rendering_mode=False,
                               fixed_delta_seconds=.05)

    def get_blueprint_library(self):
        return self

    def find(self, name):
        if name != "sensor.camera.rgb":
            raise ValueError("Wrong sensor")
        blueprint = Blueprint()
        self.blueprints.append(blueprint)
        return blueprint

    def spawn_actor(self, blueprint, transform, **kwargs):
        sensor = Sensor()
        self.sensors.append(sensor)
        self.spawns.append((transform, kwargs))
        return sensor


class CameraRigTests(unittest.TestCase):
    def setUp(self):
        self.world = World()
        self.api = SimpleNamespace(
            Location=lambda **kwargs: kwargs,
            Rotation=lambda **kwargs: kwargs,
            Transform=lambda location, rotation: (location, rotation))
        self.ego = object()
        self.names = ("overview", "approach", "reference_corner",
                      "driver_reference")
        self.site = {"cameras": [
            {"name": name, "width": 1920 if name == "overview" else 1280,
             "height": 1080 if name == "overview" else 720,
             "attachment": "ego" if name == "driver_reference" else "world",
             "reviewer": "fixture", "pose_source_citation": "fixture",
             "fov_deg": 90, "location_xyz_m": [1, 2, 3],
             "rotation_rpy_deg": [4, 5, 6]}
            for name in self.names]}

    def test_spawn_pose_and_synchronous_join(self):
        rig = NativeCameraRig(self.world, self.ego, self.api, self.site)
        self.assertEqual(len(self.world.sensors), 4)
        self.assertEqual(self.world.spawns[0][0][1],
                         {"roll": 4, "pitch": 5, "yaw": 6})
        self.assertEqual(self.world.spawns[-1][1], {"attach_to": self.ego})
        self.assertEqual(self.world.blueprints[0].attributes["image_size_x"],
                         "1920")
        for sensor, item in zip(self.world.sensors, self.site["cameras"]):
            sensor.callback(SimpleNamespace(
                frame=17, width=item["width"], height=item["height"],
                raw_data=bytes(item["width"] * item["height"] * 4)))
        self.assertEqual(set(rig.read(17, timeout_s=.01)), set(self.names))
        rig.close()
        self.assertTrue(all(s.stopped and s.destroyed for s in self.world.sensors))

    def test_wrong_frame_dimensions_fail_before_capture(self):
        rig = NativeCameraRig(self.world, self.ego, self.api, self.site)
        self.world.sensors[0].callback(SimpleNamespace(
            frame=17, width=8, height=8, raw_data=bytes(8 * 8 * 4)))
        with self.assertRaisesRegex(ValueError, "callback failed"):
            rig.read(17, timeout_s=.01)
        rig.close()

    def test_unsynchronized_frame_rejected(self):
        rig = NativeCameraRig(self.world, self.ego, self.api, self.site)
        with self.assertRaisesRegex(ValueError, "images missing"):
            rig.read(17, timeout_s=.001)
        rig.close()


if __name__ == "__main__":
    unittest.main()
