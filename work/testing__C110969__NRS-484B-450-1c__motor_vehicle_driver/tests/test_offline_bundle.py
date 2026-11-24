import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class OfflineBundleTests(unittest.TestCase):
    def test_nine_exact_case_intents_are_source_bound(self):
        plan_bytes = (ROOT / "case-plan.json").read_bytes()
        plan = json.loads(plan_bytes)
        manifest = json.loads((ROOT / "execution-manifest.draft.json").read_text())
        self.assertEqual(len(manifest["cases"]), len(plan["cases"]))
        self.assertEqual(len(plan["cases"]), 9)
        by_id = {row["case_id"]: row for row in plan["cases"]}
        for entry in manifest["cases"]:
            case = entry["case_id"]
            source = ROOT / entry["construction"]
            self.assertEqual(entry["construction_sha256"],
                             hashlib.sha256(source.read_bytes()).hexdigest())
            construction = json.loads(source.read_text())
            self.assertEqual(construction["case_id"], case)
            files = {row["path"]: row["content"] for row in construction["files"]}
            config = json.loads(files["config.json"])
            self.assertEqual(config["plan_sha256"], hashlib.sha256(plan_bytes).hexdigest())
            self.assertEqual(files["case-plan.json"].encode(), plan_bytes)
            for key in ("activity_intent", "body_destination", "exception_context"):
                self.assertEqual(config[key], by_id[case][key])
            self.assertEqual(config["frame_count"], 900)
            self.assertEqual(config["rate_hz"], 20)
            self.assertEqual(len(config["camera_dimensions"]), 4)


if __name__ == "__main__":
    unittest.main()
