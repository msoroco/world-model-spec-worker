import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from site_contract import CASE_ACTIONS


class OfflineBundleTests(unittest.TestCase):
    def test_five_exact_actions_and_original_profile(self):
        manifest = json.loads((ROOT / "execution-manifest.draft.json").read_text())
        plan = json.loads((ROOT / "case-plan.json").read_text())
        self.assertEqual({item["case_id"] for item in manifest["cases"]},
                         {item["case_id"] for item in plan["cases"]})
        for entry in manifest["cases"]:
            path = ROOT / entry["construction"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["construction_sha256"])
            construction = json.loads(path.read_text())
            files = {item["path"]: item["content"] for item in construction["files"]}
            config = json.loads(files["config.json"])
            key = entry["case_id"].removeprefix(ROOT.name + "__")
            self.assertEqual(tuple(config["action"]), CASE_ACTIONS[key])
            self.assertEqual(config["rate_hz"] * 45, config["frame_count"])
            self.assertEqual(len(config["cameras"]), 4)
            self.assertTrue(construction["diagnostic_only"])
            self.assertEqual(hashlib.sha256(files["case-plan.json"].encode()).hexdigest(), config["plan_sha256"])

    def test_bundle_source_code_is_current(self):
        manifest = json.loads((ROOT / "execution-manifest.draft.json").read_text())
        for entry in manifest["cases"]:
            construction = json.loads((ROOT / entry["construction"]).read_text())
            files = {item["path"]: item["content"] for item in construction["files"]}
            for name in ("site_contract.py", "native_capture.py", "door_interaction.py",
                         "delivery_measure.py", "delivery_audit.py", "process_saved.py", "compare_saved.py"):
                self.assertEqual(files[name], (ROOT / name).read_text())


if __name__ == "__main__":
    unittest.main()
