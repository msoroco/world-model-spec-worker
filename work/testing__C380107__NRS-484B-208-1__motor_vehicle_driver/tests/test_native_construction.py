"""CPU proof of selected controls and original-site refusal gates."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from hov_controls import selected_schedule
from package_contract import ASSIGNMENT, CAMERAS
from reviewed_site import plan
from reviewed_site import SOURCES
from runner import check_config, selected_ids


SCRATCH = Path(os.environ.get("TMPDIR", ".runtime-work/c380107-owner"))


class NativeConstruction(unittest.TestCase):
    def test_all_selected_controls_bounded(self):
        cases = selected_ids()
        self.assertEqual(len(cases), 18)
        for case in cases:
            controls = selected_schedule(case, 28.0)
            self.assertGreaterEqual(controls["ego_target_speed_mps"], 2)
            self.assertLessEqual(controls["ego_target_speed_mps"], 28)
            self.assertGreaterEqual(controls["rear_target_speed_mps"], controls["ego_target_speed_mps"])
            self.assertEqual(controls["legal_judgment"], "unresolved")

    def test_exact_config(self):
        config = {"law_id": "NRS-484B-208-1", "cell_id": "C380107",
                  "actor": "motor_vehicle_driver", "selected_case_id": sorted(selected_ids())[0],
                  "diagnostic_only": True, "rate_hz": 20, "duration_s": 45,
                  "cameras": CAMERAS}
        self.assertTrue(check_config(config))
        config["duration_s"] = 44
        with self.assertRaises(ValueError):
            check_config(config)

    def test_missing_original_source_refused(self):
        case = sorted(selected_ids())[0]
        with self.assertRaises(ValueError):
            plan(SCRATCH, {"path": "absent.json", "sha256": "0" * 64}, case)

    def test_synthetic_site_refused_even_with_valid_hash(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as name:
            root = Path(name)
            site = root / "site.json"
            site.write_text(json.dumps({"source_kind": "synthetic_cpu_fixture", "cell_id": "C380107"}) + "\n")
            ref = {"path": "site.json", "sha256": hashlib.sha256(site.read_bytes()).hexdigest()}
            with self.assertRaisesRegex(ValueError, "reviewed original"):
                plan(root, ref, sorted(selected_ids())[0])

    def test_reviewed_source_join_and_compliance_request(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as name:
            root = Path(name)
            case = sorted(selected_ids())[0]
            schedule = selected_schedule(case, 28.0)
            packets = {key: {"source_kind": "original_authority"} for key in SOURCES}
            packets["lane_geometry"] = {
                "controlled_access": True, "clearly_marked_same_direction": True,
                "same_direction_lane_ids": ["L0", "L1"], "extreme_left_lane_id": "L0",
                "right_response_lane_id": "L1"}
            packets["posted_limit"] = {"posted_limit_mps": 28.0}
            packets["hov_designation"]["state"] = schedule["hov_designation_request"]
            packets["hov_compliance"]["state"] = schedule["hov_compliance_request"]
            actor = {"blueprint_id": "vehicle.test", "spawn_pose":
                     {"x": 1.0, "y": 2.0, "z": 3.0, "yaw": 0.0}}
            packets["actor_poses"] = {"ego": actor, "rear": actor,
                                      "camera_poses": {key: {} for key in
                                                       ("overview", "approach", "reference_corner", "driver_reference")}}
            refs = {}
            for key, packet in packets.items():
                path = root / (key + ".json")
                path.write_text(json.dumps(packet) + "\n", encoding="utf-8")
                refs[key] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            site = root / "site.json"
            site.write_text(json.dumps({"source_kind": "reviewed_original_highway_site",
                                        "cell_id": "C380107", **refs}) + "\n", encoding="utf-8")
            site_ref = {"path": site.name, "sha256": hashlib.sha256(site.read_bytes()).hexdigest()}
            reviewed = plan(root, site_ref, case)
            self.assertEqual(reviewed["schedule"], schedule)
            self.assertEqual(set(reviewed["source_refs"]), set(SOURCES))
            packets["hov_compliance"]["state"] = "improper"
            path = root / "hov_compliance.json"
            path.write_text(json.dumps(packets["hov_compliance"]) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source bytes changed"):
                plan(root, site_ref, case)


if __name__ == "__main__":
    unittest.main()
