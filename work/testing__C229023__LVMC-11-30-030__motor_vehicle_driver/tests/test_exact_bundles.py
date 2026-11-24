"""Check the six sealed offline bundles against their original exact case plan."""

import hashlib
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from build_exact_bundles import CAMERAS, CASES, SOURCES
from crosswalk_measurements import ASSIGNMENT_ID


class ExactBundleTests(unittest.TestCase):
    def test_six_source_bound_constructions(self):
        manifest = json.loads((HERE / "execution-manifest.draft.json").read_text())
        current_plan = json.loads((HERE / "case-plan.json").read_text())
        self.assertEqual(manifest["status"], "diagnostic_offline_only_source_and_delivery_proofs_pending")
        self.assertEqual({row["case_id"] for row in manifest["cases"]},
                         {ASSIGNMENT_ID + "__" + suffix for suffix in CASES})
        for row in manifest["cases"]:
            with self.subTest(case_id=row["case_id"]):
                source = HERE / row["construction"]
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), row["construction_sha256"])
                construction = json.loads(source.read_text())
                self.assertTrue(construction["diagnostic_only"])
                self.assertEqual(construction["case_id"], row["case_id"])
                files = {item["path"]: item["content"] for item in construction["files"]}
                sealed_plan = json.loads(files["case-plan.json"])
                self.assertEqual(sealed_plan["cases"], current_plan["cases"])
                self.assertEqual(sealed_plan["observations"], current_plan["observations"])
                for name in SOURCES:
                    self.assertEqual(files[name], (HERE / name).read_text())
                config = json.loads(files["config.json"])
                self.assertEqual(config["plan_sha256"],
                                 hashlib.sha256(files["case-plan.json"].encode()).hexdigest())
                suffix = row["case_id"].removeprefix(ASSIGNMENT_ID + "__")
                self.assertEqual((config["crosswalk_kind"], config["ego_behavior"],
                                  config["lead_stop_purpose"]), CASES[suffix])
                self.assertEqual((config["rate_hz"], config["frame_count"], config["duration_s"]),
                                 (20, 900, 45))
                self.assertEqual(config["cameras"], list(CAMERAS))


if __name__ == "__main__":
    unittest.main()
