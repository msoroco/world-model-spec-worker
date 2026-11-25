"""CPU construction probes; synthetic source bytes have no authority."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from reviewed_scene import ASSIGNMENT, CAMERAS, VARIANTS, execute_native, plan


SCRATCH = Path(__file__).resolve().parents[3] / ".runtime-work" / "c147344-scene-tests"


class FakeAdapter:
    def __init__(self):
        self.spawned = []
        self.frames = []
        self.cameras = []

    def open_map(self, path, sha256):
        self.map = (path, sha256)

    def spawn_vehicle(self, **spec):
        self.spawned.append(spec)
        return spec["role"] + "-actor"

    def attach_camera(self, **spec):
        self.cameras.append(spec)
        return spec["name"] + "-camera"

    def tick_and_capture(self, **spec):
        self.frames.append(spec["frame"])


class ReviewedSceneTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        map_path = self.root / "map.xodr"
        map_path.write_text("<OpenDRIVE/>\n")
        self.site = {"reviewed_original_site": True, "highway": True, "one_way": True,
                     "map_ref": self.ref(map_path),
                     "same_direction_lanes": [
                         {"id": "R", "direction": "travel", "clearly_marked": True},
                         {"id": "M", "direction": "travel", "clearly_marked": True}],
                     "lane_roles": {"right": "R", "middle": "M"},
                     "construction_controls": {
                         "ego_speed_mps": 5.0, "follower_speed_mps": 8.0,
                         "slower_speed_mps": 3.0, "ego_start_station_m": 20.0,
                         "follower_start_station_m": 0.0,
                         "slower_start_station_m": 50.0}}
        self.save_site()

    def ref(self, path):
        return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def save_site(self):
        path = self.root / "site.json"
        path.write_text(json.dumps(self.site, sort_keys=True) + "\n")
        self.site_ref = self.ref(path)

    def test_four_exact_variants_construct_and_call_native_adapter(self):
        for suffix, (lane_role, follower, passing) in VARIANTS.items():
            scene = plan(self.root, self.site_ref, ASSIGNMENT + "__" + suffix)
            actor_roles = [row["role"] for row in scene["actors"]]
            self.assertEqual(scene["actors"][0]["lane_id"],
                             self.site["lane_roles"][lane_role])
            self.assertIn("following_vehicle", actor_roles)
            self.assertEqual(scene["requested_immediate_follower"], follower)
            self.assertEqual(scene["actors"][1]["lane_id"],
                             scene["actors"][0]["lane_id"] if follower else "R")
            self.assertEqual("slower_vehicle" in actor_roles, passing)
            self.assertEqual(scene["cameras"], list(CAMERAS))
            adapter = FakeAdapter()
            receipt = execute_native(scene, adapter)
            self.assertEqual(adapter.frames, list(range(900)))
            self.assertEqual(len(adapter.cameras), 4)
            self.assertFalse(receipt["physical_acceptance"])

    def test_rejects_unreviewed_or_unmarked_or_stale_source(self):
        case = ASSIGNMENT + "__slow_middle_follower"
        self.site["reviewed_original_site"] = False
        self.save_site()
        with self.assertRaisesRegex(ValueError, "original reviewed highway"):
            plan(self.root, self.site_ref, case)
        self.site["reviewed_original_site"] = True
        self.site["same_direction_lanes"][0]["clearly_marked"] = False
        self.save_site()
        with self.assertRaisesRegex(ValueError, "marked highway lanes"):
            plan(self.root, self.site_ref, case)
        self.site["same_direction_lanes"][0]["clearly_marked"] = True
        self.save_site()
        (self.root / "site.json").write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "source hash changed"):
            plan(self.root, self.site_ref, case)

    def test_rejects_wrong_lane_order_and_actor_order(self):
        case = ASSIGNMENT + "__slow_middle_passing"
        self.site["lane_roles"]["right"] = "M"
        self.save_site()
        with self.assertRaisesRegex(ValueError, "lane ordering"):
            plan(self.root, self.site_ref, case)
        self.site["lane_roles"]["right"] = "R"
        self.site["construction_controls"]["follower_start_station_m"] = 25.0
        self.save_site()
        with self.assertRaisesRegex(ValueError, "actor ordering"):
            plan(self.root, self.site_ref, case)


if __name__ == "__main__":
    unittest.main()
