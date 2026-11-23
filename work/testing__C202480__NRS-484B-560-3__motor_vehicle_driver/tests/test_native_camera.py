"""CPU fake proof of four RGB source files and sensor closure."""

import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as Box
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from native_camera import CameraRig, VIEWS, validate_plan


def camera_packet():
    return {"cameras": [
        {"name": name, "width": width, "height": height,
         "attachment": "ego" if name == "driver_reference" else "world",
         "pose_source_citation": "synthetic fixture pose", "reviewer": "CPU fixture",
         "location_xyz_m": [0., 0., 2.], "rotation_rpy_deg": [0., 0., 0.],
         "fov_deg": 90.} for name, width, height in VIEWS]}


class Blueprint:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, name, value):
        self.attributes[name] = value


class Sensor:
    def __init__(self, blueprint, attachment):
        self.blueprint, self.attachment = blueprint, attachment
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
        private = ROOT / ".runtime-work"
        private.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=private)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.packet = self.folder / "packet.json"
        self.packet.write_text(json.dumps(camera_packet()) + "\n")

    def test_four_source_bytes_and_cleanup(self):
        world = World()
        ego = object()
        rig = CameraRig(world, ego, self.packet, self.folder / "raw",
                        lambda location, rotation: (location, rotation))
        self.assertEqual(len(world.sensors), 4)
        self.assertIs(world.sensors[-1].attachment, ego)
        for sensor, (name, width, height) in zip(world.sensors, VIEWS):
            self.assertEqual(sensor.blueprint.attributes["image_size_x"], str(width))
            sensor.callback(Box(frame=400, timestamp=20., width=width, height=height,
                                raw_data=b"\0" * (width * height * 4)))
        sources = rig.await_frame(400, 20.)
        self.assertEqual(set(sources), {name for name, _, _ in VIEWS})
        self.assertTrue(all((self.folder / "raw" / item["raw_bgra"]).is_file()
                            for item in sources.values()))
        rig.close()
        self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in world.sensors))

    def test_unreviewed_camera_pose_and_bad_pixels_rejected(self):
        packet = camera_packet()
        packet["cameras"][0]["pose_source_citation"] = ""
        self.packet.write_text(json.dumps(packet) + "\n")
        with self.assertRaisesRegex(ValueError, "camera identity, size or source"):
            validate_plan(self.packet)
        self.packet.write_text(json.dumps(camera_packet()) + "\n")
        world = World()
        rig = CameraRig(world, object(), self.packet, self.folder / "raw",
                        lambda location, rotation: (location, rotation))
        name, width, height = VIEWS[0]
        world.sensors[0].callback(Box(frame=400, timestamp=20., width=width,
                                      height=height, raw_data=b"bad"))
        with self.assertRaisesRegex(ValueError, "raw pixels differ"):
            rig.await_frame(400, 20., timeout_s=.01)
        rig.close()


if __name__ == "__main__":
    unittest.main()
