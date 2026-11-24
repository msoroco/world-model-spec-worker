"""Exact-case diagnostic bundle inventory checks."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_offline_draft", HERE / "build_offline_draft.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class OfflineDraftTests(unittest.TestCase):
    def test_seven_source_bound_exact_bundles(self):
        plan_bytes = (HERE / "case-plan.json").read_bytes()
        plan = json.loads(plan_bytes)
        draft = json.loads((HERE / "execution-manifest.draft.json").read_text())
        self.assertEqual({row["case_id"] for row in draft["cases"]},
                         {row["case_id"] for row in plan["cases"]})
        self.assertEqual(len(draft["cases"]), 7)
        by_case = {row["case_id"]: row for row in plan["cases"]}
        for entry in draft["cases"]:
            construction_path = HERE / entry["construction"]
            construction_bytes = construction_path.read_bytes()
            self.assertEqual(hashlib.sha256(construction_bytes).hexdigest(),
                             entry["construction_sha256"])
            construction = json.loads(construction_bytes)
            self.assertTrue(construction["diagnostic_only"])
            self.assertEqual(construction["case_id"], entry["case_id"])
            files = {row["path"]: row["content"] for row in construction["files"]}
            self.assertEqual(set(MODULE.SOURCES) | {"runner.py", "case-plan.json",
                                                     "config.json", "tests/test_bundle.py"}, set(files))
            for source in MODULE.SOURCES:
                self.assertEqual(files[source], (HERE / source).read_text())
            config = json.loads(files["config.json"])
            self.assertEqual(config["plan_sha256"], hashlib.sha256(plan_bytes).hexdigest())
            self.assertEqual((config["requested_front_body_gap_ft"], config["activity"],
                              config["halt_cause"]),
                             tuple(by_case[entry["case_id"]][key] for key in
                                   ("requested_front_body_gap_ft", "activity", "halt_cause")))


if __name__ == "__main__":
    unittest.main()
