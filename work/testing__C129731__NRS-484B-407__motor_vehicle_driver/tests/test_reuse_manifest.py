import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from build_reuse_manifest import build


class SelectedReuseManifestTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((HERE / "case-plan.json").read_text())

    def test_exact_frozen_ten_and_seven_match_committed_inventory(self):
        actual = build(self.plan, ROOT, HERE)
        committed = json.loads((HERE / "selected-reuse-manifest.json").read_text())
        self.assertEqual(actual, committed)
        self.assertEqual(len(actual["candidates"]), 10)
        self.assertEqual(len(actual["comparisons"]), 7)
        self.assertEqual(actual["new_recordings_planned"], 0)
        self.assertEqual(actual["canonical_acceptance"], "not_performed_here")
        for row in actual["candidates"]:
            command = row["command_template"]
            self.assertEqual(command[command.index("--case") + 1], row["case_id"])
            self.assertEqual(command[command.index("--recording") + 1], row["recording_id"])
            self.assertEqual(command[command.index("--sight-attempt") + 1],
                             "{original_sight_attempt}")
        for row in actual["comparisons"]:
            command = row["command_template"]
            self.assertEqual(command[command.index("--comparison") + 1],
                             row["comparison_id"])

    def test_wrong_frozen_hash_or_pair_rejected(self):
        self.plan["sources"][3]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "metadata hash"):
            build(self.plan, ROOT, HERE)
        self.plan = json.loads((HERE / "case-plan.json").read_text())
        self.plan["accepted_comparisons_pending_original_review"][0]["recording_ids"][0] = "0" * 64
        with self.assertRaisesRegex(ValueError, "comparison identity"):
            build(self.plan, ROOT, HERE)


if __name__ == "__main__":
    unittest.main()
