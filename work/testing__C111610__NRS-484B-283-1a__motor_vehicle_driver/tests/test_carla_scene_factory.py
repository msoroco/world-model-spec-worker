"""Focused source gate, four-camera and live control tests with fake CARLA API."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

import carla_scene_factory as factory
from test_saved_measurement import packet


SCENE = ROOT / "scenes" / "destination_occupied_absent.json"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


class Blueprint:
    def __init__(self): self.attributes = {}
    def set_attribute(self, key, value): self.attributes[key] = value


class Actor:
    def __init__(self, actor_id, x=0, y=0):
        self.id = actor_id
        self.location = SimpleNamespace(x=x, y=y)
        self.control = SimpleNamespace(brake=0)
        self.commands = []
    def get_transform(self):
        return SimpleNamespace(location=self.location,
                               get_forward_vector=lambda: SimpleNamespace(x=1, y=0))
    def get_control(self): return self.control
    def get_velocity(self): return SimpleNamespace(x=0, y=0)
    def apply_control(self, command): self.commands.append(command)
    def listen(self, callback): self.callback = callback


class World:
    def __init__(self): self.actors = []
    def get_map(self): return SimpleNamespace(name="SourceTown")
    def get_snapshot(self): return SimpleNamespace(frame=0)
    def get_blueprint_library(self): return SimpleNamespace(find=lambda _: Blueprint())
    def spawn_actor(self, blueprint, pose, attach_to=None):
        actor = Actor(100 + len(self.actors))
        self.actors.append(actor)
        return actor


API = SimpleNamespace(
    Location=lambda *args: args, Rotation=lambda *args: args,
    Transform=lambda a, b: (a, b),
    VehicleControl=lambda **kwargs: SimpleNamespace(**kwargs),
    WalkerControl=lambda **kwargs: SimpleNamespace(**kwargs),
    Vector3D=lambda **kwargs: SimpleNamespace(**kwargs))


class FactoryTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".runtime-work" / "c111610-factory-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scene = json.loads(SCENE.read_text())
        self.site = packet()
        self.site["crosswalk"]["polygon_xy_m"] = [[2, 0], [6, 0], [6, 5], [2, 5]]
        self.site["lanes"][0]["polygon_xy_m"] = [[2, 0], [4, 0], [4, 9], [2, 9]]
        self.site["lanes"][1]["polygon_xy_m"] = [[4, 0], [6, 0], [6, 9], [4, 9]]
        self.site["lanes"][2]["polygon_xy_m"] = [[6, 0], [8, 0], [8, 9], [6, 9]]
        self.site["pedestrian_routes"] = {
            self.scene["case_id"]: {"source": "original_map_and_local_review",
                                    "waypoints": [[4.0, 1.0], [4.0, 3.0]]}}
        self.exception = {"case_id": self.scene["case_id"],
                          "status": "none_identified", "source_refs": ["review/exceptions"]}
        self.world = World()

    def files(self):
        paths = [self.root / name for name in ("scene.json", "site.json", "exception.json")]
        for path, value in zip(paths, (self.scene, self.site, self.exception)):
            path.write_text(json.dumps(value) + "\n")
        return paths

    def build(self):
        ego, pedestrian = Actor(1, 0, -2), Actor(2, 4, 1)
        with patch.object(factory, "construct", return_value={"ego": ego,
                                                                 "pedestrian": pedestrian}):
            scene = factory.make_scene_factory(API, dimensions={name: (2, 2)
                                           for name in CAMERAS})(
                world=self.world, scene_path=self.files()[0],
                site_path=self.root / "site.json",
                exception_path=self.root / "exception.json",
                register=lambda actor: actor)
        return scene

    def test_four_source_cameras_and_engineering_hold(self):
        scene = self.build()
        self.assertEqual(set(scene["sensors"]), set(CAMERAS))
        for sensor in scene["sensors"].values():
            self.assertEqual(sensor.callback is not None, True)
            self.assertEqual(sensor.id >= 100, True)
        scene["controller"](self.world, scene["ego"], scene["pedestrian"])
        self.assertGreaterEqual(scene["ego"].commands[-1].brake, .8)
        self.assertEqual(scene["pedestrian"].commands[-1].speed, 1.0)

    def test_source_gate_rejects_missing_route_and_wrong_device(self):
        with_route = self.site.copy()
        self.site.pop("pedestrian_routes")
        with self.assertRaisesRegex(ValueError, "pedestrian route missing"):
            self.build()
        self.site = with_route
        self.scene["official_device_condition"] = "operating"
        with self.assertRaisesRegex(ValueError, "device condition differs"):
            self.build()

    def test_source_gate_rejects_wrong_crosswalk_region(self):
        self.site["crosswalk"]["polygon_xy_m"] = [[-2, 0], [0, 0], [0, 5], [-2, 5]]
        with self.assertRaisesRegex(ValueError, "wrong crosswalk region"):
            self.build()

    def test_original_frame_and_bgra_decode(self):
        sensor = Actor(5)
        reader = factory.CameraReader(sensor, (2, 2))
        sensor.callback(SimpleNamespace(frame=42, width=2, height=2,
                                        raw_data=bytes([10, 20, 30, 255] * 4)))
        value = reader(42)
        from io import BytesIO
        with Image.open(BytesIO(value["png_bytes"])) as image:
            self.assertEqual(image.size, (2, 2))
            self.assertEqual(image.getpixel((0, 0)), (30, 20, 10))
        sensor.callback(SimpleNamespace(frame=44, width=2, height=2,
                                        raw_data=bytes([0, 0, 0, 255] * 4)))
        with self.assertRaisesRegex(ValueError, "frame mismatch"):
            reader(43)


if __name__ == "__main__": unittest.main()
