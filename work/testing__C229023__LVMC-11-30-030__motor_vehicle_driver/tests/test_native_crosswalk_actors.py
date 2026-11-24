import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import native_crosswalk_actors as module
from crosswalk_measurements import ASSIGNMENT_ID


class Vec:
    def __init__(self, x=0, y=0, z=0):
        self.x, self.y, self.z = x, y, z


class Actor:
    def __init__(self, identifier, transform):
        self.id = identifier
        self.location = transform[0]
        self.transform = type("Transform", (), {"rotation": type("Rotation", (), {"yaw": transform[1]["yaw"]})()})()
        self.velocity = Vec()
        self.controls = []
        self.destroyed = False
        self.bounding_box = type("Box", (), {"get_world_vertices": lambda self, transform: [Vec(index, 0, 0) for index in range(8)]})()

    def get_location(self):
        return self.location

    def get_transform(self):
        return self.transform

    def get_velocity(self):
        return self.velocity

    def apply_control(self, control):
        self.controls.append(control)

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.spawned = []
        self.fail_role = None

    def get_blueprint_library(self):
        return self

    def find(self, identifier):
        return identifier

    def try_spawn_actor(self, blueprint, transform):
        if self.fail_role and blueprint == self.fail_role:
            return None
        actor = Actor(len(self.spawned) + 10, transform)
        self.spawned.append(actor)
        return actor


class Carla:
    Location = staticmethod(lambda **parts: Vec(**parts))
    Rotation = staticmethod(lambda **parts: parts)
    Transform = staticmethod(lambda location, rotation: (location, rotation))
    VehicleControl = staticmethod(lambda **parts: parts)
    WalkerControl = staticmethod(lambda **parts: parts)
    Vector3D = staticmethod(lambda **parts: Vec(**parts))


class NativeActorTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.case_id = ASSIGNMENT_ID + "__unmarked_pass"
        self.plan = {"case_id": self.case_id, "map_id": "TownReviewed",
                     "blueprints": {"ego": "vehicle.test.ego", "lead": "vehicle.test.lead",
                                    "pedestrian": "walker.pedestrian.test"},
                     "spawn_z_m": {"ego": 0.3, "lead": 0.3, "pedestrian": 0.2},
                     "ego_target_speed_mps": 5.0, "pedestrian_speed_mps": 1.0}
        self.actor_file = self.root / "actor-setup.json"
        self.actor_file.write_text(json.dumps(self.plan))
        site = {"sources": {"actor_setup": {"path": self.actor_file.name,
                                             "sha256": hashlib.sha256(self.actor_file.read_bytes()).hexdigest(),
                                             "citation": "reviewed original actor setup"}}}
        self.site_file = self.root / "site.json"
        self.site_file.write_text(json.dumps(site))
        self.proposal = {"assignment_id": ASSIGNMENT_ID, "case_id": self.case_id,
                         "source": {"path": str(self.site_file), "sha256": hashlib.sha256(self.site_file.read_bytes()).hexdigest()},
                         "map_id": "TownReviewed", "ego_route": [[0, 0], [10, 2], [20, 2]],
                         "lead_stop_center": [8, 0], "pedestrian_route": [[11, -4], [11, 4]],
                         "ego_behavior": "pass"}

    def test_spawn_control_observe_cleanup(self):
        world = World()
        actors = module.NativeCrosswalkActors(world=world, carla=Carla, proposal=self.proposal)
        self.assertEqual(actors.actor_ids, {"ego": "10", "lead": "11", "pedestrian": "12"})
        actors.control()
        self.assertEqual(world.spawned[1].controls[-1]["brake"], 1.0)
        self.assertEqual(world.spawned[2].controls[-1]["speed"], 1.0)
        rows = actors.observe(100)
        self.assertEqual(len(rows["ego"]["vertices"]), 8)
        self.assertIn("frame/100", rows["pedestrian"]["source_ref"])
        actors.close()
        actors.close()
        self.assertTrue(all(actor.destroyed for actor in world.spawned))

    def test_changed_source_and_map_rejected(self):
        self.actor_file.write_text("{}")
        with self.assertRaisesRegex(ValueError, "source changed"):
            module.NativeCrosswalkActors(world=World(), carla=Carla, proposal=self.proposal)
        self.actor_file.write_text(json.dumps(self.plan))
        self.proposal["map_id"] = "OtherMap"
        with self.assertRaisesRegex(ValueError, "map or exact case"):
            module.NativeCrosswalkActors(world=World(), carla=Carla, proposal=self.proposal)

    def test_partial_spawn_is_cleaned(self):
        world = World()
        world.fail_role = "walker.pedestrian.test"
        with self.assertRaisesRegex(RuntimeError, "spawn failed"):
            module.NativeCrosswalkActors(world=world, carla=Carla, proposal=self.proposal)
        self.assertTrue(all(actor.destroyed for actor in world.spawned))


if __name__ == "__main__":
    unittest.main()
