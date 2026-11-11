"""Independent subprocess checks of the assignment-level executable package."""
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RootSelectedPackageTest(unittest.TestCase):
    def test_case_support_and_exact_camera_contract(self):
        config = json.loads((ROOT / "config.json").read_text())
        prefix = config["case_id"].rsplit("__", 1)[0]
        self.assertEqual(set(config["supported_case_ids"]),
                         {prefix + "__reference", prefix + "__contrast"})
        self.assertEqual(config["case_id"], prefix + "__reference")
        self.assertEqual(
            [(camera["name"], camera["width"], camera["height"], camera["fov_deg"])
             for camera in config["cameras"]],
            [("overview", 1920, 1080, 90), ("approach", 1280, 720, 95),
             ("reference_corner", 1280, 720, 90),
             ("driver_reference", 1280, 720, 90)],
        )
        self.assertTrue(all(camera["pose_strategy"] for camera in config["cameras"]))

    def test_entrypoint_checks_without_native_import_or_physical_claim(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "runner.py"), "--check"],
            cwd=ROOT, text=True, capture_output=True, check=True,
        )
        report = json.loads(result.stdout)
        self.assertEqual(report["candidate"], "primary")
        self.assertEqual(report["camera_count"], 4)
        self.assertFalse(report["native_imported"])
        self.assertFalse(report["physical_success_claimed"])


if __name__ == "__main__":
    unittest.main()
