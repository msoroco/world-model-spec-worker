"""Fallbacks preserve exact-case evidence while changing one controller knob."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def config(construction):
    return json.loads(next(item["content"] for item in construction["files"]
                           if item["path"] == "config.json"))


class CandidateIsolation(unittest.TestCase):
    def test_both_pairs_keep_case_and_observations(self):
        for suffix in ("probe_1", "probe_2"):
            with self.subTest(case=suffix):
                primary = json.loads((ROOT / "draft-exact" / suffix / "primary" /
                                      "construction.json").read_text())
                fallback = json.loads((ROOT / "draft-exact" / suffix / "fallback1" /
                                       "construction.json").read_text())
                self.assertEqual(primary["case_id"], fallback["case_id"])
                self.assertEqual(primary["recording_description"],
                                 fallback["recording_description"])
                self.assertEqual({item["path"] for item in primary["files"]},
                                 {item["path"] for item in fallback["files"]})
                old, new = config(primary), config(fallback)
                self.assertEqual(old.pop("controller_throttle_scale"), 1.0)
                self.assertEqual(new.pop("controller_throttle_scale"), 0.8)
                self.assertEqual(old, new)

    def test_fallback_trigger_is_measured(self):
        manifest = json.loads((ROOT / "draft-native-manifest.json").read_text())
        self.assertFalse(manifest["delivery_ready"])
        for case in manifest["cases"]:
            self.assertEqual(case["candidate_risk"]["status"], "physical")
            fallback, = case["candidates"]
            self.assertIn("native-rows.jsonl", fallback["trigger"]["source"])
            self.assertIn("2 feet", fallback["trigger"]["failure_condition"])


if __name__ == "__main__":
    unittest.main()
