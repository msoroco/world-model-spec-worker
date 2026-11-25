"""CPU construction probes; synthetic source bytes have no authority."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from reviewed_scene import ASSIGNMENT, CAMERAS, VARIANTS, execute_native, main, plan


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
        map_path.write_text('<OpenDRIVE><road id="21"><lanes><laneSection><right>'
                            '<lane id="-1" type="driving"/><lane id="-2" type="driving"/>'
                            '</right></laneSection></lanes></road></OpenDRIVE>\n')
        pose = {key: 0.0 for key in ("x", "y", "z", "pitch", "yaw", "roll")}
        self.site = {"reviewed_original_site": True, "highway": True, "one_way": True,
                     "map_ref": self.ref(map_path), "road_id": "21",
                     "same_direction_lanes": [
                         {"id": "-1", "direction": "travel", "clearly_marked": True},
                         {"id": "-2", "direction": "travel", "clearly_marked": True}],
                     "lane_roles": {"right": "-1", "middle": "-2"},
                     "camera_profiles": {name: {"width": 960, "height": 540,
                                                "pose": pose} for name in CAMERAS},
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
                             scene["actors"][0]["lane_id"] if follower else "-1")
            self.assertEqual("slower_vehicle" in actor_roles, passing)
            self.assertEqual(set(scene["cameras"]), set(CAMERAS))
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
        self.site["lane_roles"]["right"] = "-2"
        self.save_site()
        with self.assertRaisesRegex(ValueError, "lane ordering"):
            plan(self.root, self.site_ref, case)
        self.site["lane_roles"]["right"] = "-1"
        self.site["construction_controls"]["follower_start_station_m"] = 25.0
        self.save_site()
        with self.assertRaisesRegex(ValueError, "actor ordering"):
            plan(self.root, self.site_ref, case)

    def test_rejects_map_lane_or_camera_profile_gap(self):
        case = ASSIGNMENT + "__slow_right_follower"
        self.site["same_direction_lanes"][1]["id"] = "-3"
        self.site["lane_roles"]["middle"] = "-3"
        self.save_site()
        with self.assertRaisesRegex(ValueError, "absent from original OpenDRIVE"):
            plan(self.root, self.site_ref, case)
        self.site["same_direction_lanes"][1]["id"] = "-2"
        self.site["lane_roles"]["middle"] = "-2"
        self.site["camera_profiles"].pop("driver_reference")
        self.save_site()
        with self.assertRaisesRegex(ValueError, "camera profiles missing"):
            plan(self.root, self.site_ref, case)

    def test_cli_writes_four_source_identical_plans_once(self):
        ref_path = self.root / "site-ref.json"
        ref_path.write_text(json.dumps(self.site_ref) + "\n")
        output = self.root.parent / (self.root.name + "-plans")
        self.addCleanup(lambda: __import__("shutil").rmtree(output, ignore_errors=True))
        argv = ["reviewed_scene.py", "--authority-root", str(self.root),
                "--site-ref", str(ref_path), "--output-root", str(output)]
        with patch("sys.argv", argv):
            main()
        self.assertEqual({p.stem for p in output.glob("*.json")}, set(VARIANTS))
        with patch("sys.argv", argv):
            with self.assertRaisesRegex(ValueError, "fresh scene output"):
                main()


if __name__ == "__main__":
    unittest.main()
