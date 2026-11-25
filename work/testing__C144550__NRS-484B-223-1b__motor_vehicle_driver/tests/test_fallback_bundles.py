import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bundle_builder import construct


class FallbackBundleTests(unittest.TestCase):
    def test_same_controller_tuning_only_across_three_exact_cases(self):
        for variant in ("both_observed", "signal_missing", "check_missing"):
            primary = construct(variant)
            fallback = construct(variant, "fallback1")
            self.assertEqual(primary["case_id"], fallback["case_id"])
            self.assertEqual(primary["recording_description"],
                             fallback["recording_description"])
            before = {item["path"]: item["content"] for item in primary["files"]}
            after = {item["path"]: item["content"] for item in fallback["files"]}
            changed = [name for name in before if before[name] != after[name]]
            self.assertEqual(changed, ["native_construction.py"])
            self.assertIn("0.85 * error", after[changed[0]])
            self.assertIn("throttle=0.0 if arrived else 0.22", after[changed[0]])
            self.assertEqual(json.loads(before["config.json"]),
                             json.loads(after["config.json"]))


if __name__ == "__main__":
    unittest.main()
