import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as Obj

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_case_constructor import construct_case
from sight_measurement import ASSIGNMENT


CASE = ASSIGNMENT + "__distance_below_500ft"


def transform(x, y, z, yaw):
    return Obj(location=Obj(x=x, y=y, z=z), rotation=Obj(yaw=yaw))


class Actor:
    def __init__(self, actor_id, blueprint):
        self.id = actor_id
        self.type_id = blueprint
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.spawned = []
        self.fail_second = False
        self.lane_id = -1

    def get_map(self):
        return Obj(to_opendrive=lambda: "reviewed mountain OpenDRIVE",
                   get_waypoint=lambda location, project_to_road=False: Obj(
                       road_id=17, lane_id=self.lane_id))

    def get_settings(self):
        return Obj(synchronous_mode=True, fixed_delta_seconds=0.05)

    def try_spawn_actor(self, blueprint, pose):
        if self.fail_second and len(self.spawned) == 1:
            return None
        actor = Actor(len(self.spawned) + 1, blueprint)
        self.spawned.append(actor)
        return actor


def reviewed_site():
    return {
        "map_source_sha256": hashlib.sha256(b"reviewed mountain OpenDRIVE").hexdigest(),
        "ego_blueprint_id": "vehicle.ego", "approach_blueprint_id": "vehicle.approach",
        "case_setups": {CASE: {
            "target_first_turn_distance_ft": 499,
            "ego_spawn": {"location": {"x": 0.0, "y": 0.0, "z": 0.0},
                          "yaw_deg": 0.0, "road_id": 17, "lane_id": -1},
            "approach_spawn": {"location": {"x": 152.0952, "y": 0.0, "z": 0.0},
                               "yaw_deg": 180.0, "road_id": 17, "lane_id": -1},
        }},
    }


class NativeCaseConstructorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "site.json"
        self.path.write_text(json.dumps(reviewed_site()) + "\n")
        self.digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.world = World()
        self.blueprints = Obj(find=lambda name: name)

    def run_construction(self):
        return construct_case(self.world, self.blueprints, self.path,
                              self.digest, CASE, transform)

    def test_exact_case_spawns_two_reviewed_vehicle_roles(self):
        ego, approach = self.run_construction()
        self.assertEqual((ego.type_id, approach.type_id),
                         ("vehicle.ego", "vehicle.approach"))
        self.assertEqual((ego.id, approach.id), (1, 2))

    def test_wrong_lane_and_distance_setup_rejected_without_spawn(self):
        self.world.lane_id = 4
        with self.assertRaisesRegex(ValueError, "road lane"):
            self.run_construction()
        self.assertEqual(self.world.spawned, [])
        bad = reviewed_site()
        bad["case_setups"][CASE]["target_first_turn_distance_ft"] = 500
        self.path.write_text(json.dumps(bad) + "\n")
        self.digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.world.lane_id = -1
        with self.assertRaisesRegex(ValueError, "distance case setup"):
            self.run_construction()
        self.assertEqual(self.world.spawned, [])

    def test_stale_site_and_failed_second_spawn_cleanup(self):
        self.path.write_text(json.dumps(dict(reviewed_site(), extra="tampered")) + "\n")
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            self.run_construction()
        self.path.write_text(json.dumps(reviewed_site()) + "\n")
        self.world.fail_second = True
        with self.assertRaisesRegex(ValueError, "spawn failed"):
            self.run_construction()
        self.assertTrue(self.world.spawned[0].destroyed)


if __name__ == "__main__":
    unittest.main()
