"""Fake Native lifecycle checks; no synthetic site is accepted as original."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parents[1] / ".runtime-work"
sys.path.insert(0, str(ROOT))

from native_session import OpposingSession, review_live_site
from test_opposing_pass import site


class Blueprint:
    def set_attribute(self, key, value):
        pass


class Actor:
    def __init__(self, ident):
        self.id = ident
        self.destroyed = False
        self.controls = []
        self.bounding_box = SimpleNamespace(get_world_vertices=lambda _: [])

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=0, y=0),
                               rotation=SimpleNamespace(yaw=0))

    def apply_control(self, value):
        self.controls.append(value)

    def destroy(self):
        self.destroyed = True


class Sensor(Actor):
    def listen(self, callback):
        self.callback = callback

    def stop(self):
        pass


class World:
    def __init__(self):
        self.settings = SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=.1)
        self.mutations = 0
        self.actors = []
        self.map = SimpleNamespace(name="ReviewedTown", to_opendrive=lambda: "reviewed-xodr")

    def get_settings(self):
        return SimpleNamespace(**vars(self.settings))

    def apply_settings(self, settings):
        self.mutations += 1
        self.settings = SimpleNamespace(**vars(settings))

    def get_map(self):
        return self.map

    def get_blueprint_library(self):
        return SimpleNamespace(find=lambda _: Blueprint())

    def try_spawn_actor(self, blueprint, transform):
        actor = Actor(len(self.actors)+1)
        self.actors.append(actor)
        return actor

    def spawn_actor(self, blueprint, transform, attach_to=None):
        actor = Sensor(len(self.actors)+1)
        self.actors.append(actor)
        return actor


class SessionTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.world = World()
        packet = site()
        packet["native_road_frame"] = {"source_id": "reviewed-axis",
            "origin_xyz_m": [0, 0, 0], "forward_xy": [1, 0]}
        packet["reviewed_provenance"] = {"reviewer": "diagnostic reviewer",
            "source_citation": "diagnostic-only fake site", "native_map_name": "ReviewedTown",
            "opendrive_sha256": hashlib.sha256(b"reviewed-xodr").hexdigest()}
        packet["camera_poses_xyz_pitch_yaw"] = {name: [0, 0, 10, -30, 0]
            for name in ("overview", "approach", "reference_corner", "driver_reference")}
        packet["native_spawn"] = {"right_half": {
            "ego": {"blueprint_id": "vehicle.a", "pose_xyz_ypr": [0, -1.7, 0, 0, 0, 0],
                    "source_id": "diagnostic-ego"},
            "other": {"blueprint_id": "vehicle.b", "pose_xyz_ypr": [30, 1.7, 0, 180, 0, 0],
                      "source_id": "diagnostic-other"}}}
        self.path = Path(self.temp.name) / "map.json"
        self.path.write_text(json.dumps(packet) + "\n")
        self.digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.carla = SimpleNamespace(Location=lambda **kw: SimpleNamespace(**kw),
            Rotation=lambda **kw: SimpleNamespace(**kw),
            Transform=lambda location, rotation: SimpleNamespace(location=location, rotation=rotation),
            VehicleControl=lambda **kw: SimpleNamespace(**kw))

    def test_site_gate_before_world_mutation(self):
        packet = json.loads(self.path.read_text())
        del packet["reviewed_provenance"]
        self.path.write_text(json.dumps(packet) + "\n")
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "reviewed median-opening provenance"):
            with OpposingSession(self.world, self.carla, self.path, digest, "right_half"):
                pass
        self.assertEqual(self.world.mutations, 0)
        self.assertFalse(self.world.actors)

    def test_live_xodr_gate_and_owned_cleanup(self):
        self.world.map.to_opendrive = lambda: "different-xodr"
        with self.assertRaisesRegex(ValueError, "OpenDRIVE bytes differ"):
            review_live_site(self.world, self.path, self.digest, "right_half")
        self.assertEqual(self.world.mutations, 0)
        self.world.map.to_opendrive = lambda: "reviewed-xodr"
        with OpposingSession(self.world, self.carla, self.path, self.digest, "right_half") as session:
            self.assertEqual(len(self.world.actors), 6)
            self.assertEqual(set(session.cameras.queues),
                {"overview", "approach", "reference_corner", "driver_reference"})
            session.control(self.world, session.actors["ego"], session.actors["other"])
            self.assertTrue(session.actors["ego"].controls)
        self.assertTrue(session.restoration_verified)
        self.assertTrue(all(actor.destroyed for actor in self.world.actors))
        self.assertFalse(self.world.settings.synchronous_mode)


if __name__ == "__main__":
    unittest.main()
