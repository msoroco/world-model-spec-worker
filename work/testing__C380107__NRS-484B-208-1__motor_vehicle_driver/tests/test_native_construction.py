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


if __name__ == "__main__":
    unittest.main()
