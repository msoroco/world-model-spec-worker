import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as Box
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from native_camera import CameraRig, VIEWS, validate_plan
from test_native_scene import packet


def camera_packet():
    document = packet()
    document["cameras"] = [
        {"name": name, "width": width, "height": height,
         "attachment": "ego" if name == "driver_reference" else "world",
         "pose_source_citation": "fixture pose", "reviewer": "fixture reviewer",
         "location_xyz_m": [0.0, 0.0, 2.0], "rotation_rpy_deg": [0.0, 0.0, 0.0],
         "fov_deg": 90.0} for name, width, height in VIEWS]
    return document


class Blueprint:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, name, value):
        self.attributes[name] = value


class Sensor:
    def __init__(self, blueprint, attachment):
        self.blueprint = blueprint
        self.attachment = attachment
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

    def get_settings(self):
        return Box(synchronous_mode=True, no_rendering_mode=False,
                   fixed_delta_seconds=.05)

    def get_blueprint_library(self):
        return Box(find=lambda name: Blueprint())

    def spawn_actor(self, blueprint, transform, **kwargs):
        sensor = Sensor(blueprint, kwargs.get("attach_to"))
        self.sensors.append(sensor)
        return sensor


class NativeCameraTests(unittest.TestCase):
    def setUp(self):
        self.root = HERE.parents[1] / ".runtime-work"
        self.root.mkdir(exist_ok=True)

    def test_four_camera_spawn_capture_join_and_cleanup(self):
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            path = Path(directory) / "packet.json"
            path.write_text(json.dumps(camera_packet()))
            world = World()
            ego = object()
            rig = CameraRig(world, ego, path, Path(directory) / "raw",
                            lambda location, rotation: (location, rotation))
            self.assertEqual(len(world.sensors), 4)
            self.assertIs(world.sensors[-1].attachment, ego)
            for sensor, (name, width, height) in zip(world.sensors, VIEWS):
                self.assertEqual(sensor.blueprint.attributes["image_size_x"], str(width))
                sensor.callback(Box(frame=400, timestamp=20.0, width=width, height=height,
                                    raw_data=b"\x00" * (width * height * 4)))
            result = rig.await_frame(400, 20.0)
            self.assertEqual(set(result), {name for name, _, _ in VIEWS})
            self.assertTrue(all((Path(directory) / "raw" / value["raw_bgra"]).exists()
                                for value in result.values()))
            rig.close()
            self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in world.sensors))

    def test_unreviewed_pose_and_bad_pixels_rejected(self):
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            path = Path(directory) / "packet.json"
            document = camera_packet()
            document["cameras"][0]["pose_source_citation"] = ""
            path.write_text(json.dumps(document))
            with self.assertRaisesRegex(ValueError, "camera identity, size or source"):
                validate_plan(path)
            path.write_text(json.dumps(camera_packet()))
            world = World()
            rig = CameraRig(world, object(), path, Path(directory) / "raw",
                            lambda location, rotation: (location, rotation))
            name, width, height = VIEWS[0]
            world.sensors[0].callback(Box(frame=400, timestamp=20.0,
                                          width=width, height=height, raw_data=b"bad"))
            with self.assertRaisesRegex(ValueError, "raw pixels differ"):
                rig.await_frame(400, 20.0, timeout_s=.01)
            rig.close()


if __name__ == "__main__":
    unittest.main()
