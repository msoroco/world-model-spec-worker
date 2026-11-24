"""Verify source-gated exact speed constructions before offline materialization."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("c10301_bundle", ROOT / "build_offline_draft.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BundleTests(unittest.TestCase):
    def test_exact_cases_and_speed_requests(self):
        MODULE.build()
        manifest = json.loads((ROOT / "execution-manifest.draft.json").read_text())
        self.assertEqual(len(manifest["cases"]), 3)
        for suffix, speed in MODULE.EXPECTED.items():
            construction = json.loads((ROOT / f"construction-{suffix}.json").read_text())
            files = {row["path"]: row["content"] for row in construction["files"]}
            config = json.loads(files["config.json"])
            self.assertEqual(config["requested_speed_mph"], speed)
            self.assertEqual(construction["case_id"], ROOT.name + "__" + suffix)
            self.assertTrue(config["diagnostic_only"])
            self.assertIn("Reviewed C10301 route", files["runner.py"])


if __name__ == "__main__":
    unittest.main()
