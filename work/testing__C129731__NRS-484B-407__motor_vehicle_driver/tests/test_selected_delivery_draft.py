import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from build_selected_delivery_draft import build


class SelectedDeliveryDraftTests(unittest.TestCase):
    def test_deterministic_exact_cases_and_source_seals(self):
        actual = build(PACKAGE)
        committed = json.loads((PACKAGE / "selected-delivery-manifest.draft.json").read_text())
        self.assertEqual(actual, committed)
        self.assertEqual(len(actual["cases"]), 4)
        self.assertEqual([case["target_first_turn_distance_ft"]
                          for case in actual["cases"]], [500, 499, 500, 501])
        self.assertEqual(actual["comparisons"][0]["case_ids"],
                         [case["case_id"] for case in actual["cases"]])
        self.assertTrue(all(case["post_capture"]["recorded_only"]
                            for case in actual["cases"]))
        self.assertTrue(all(case["delivery_acceptance"].startswith("pending")
                            for case in actual["cases"]))

    def test_rebound_case_and_distance_are_rejected(self):
        plan = json.loads((PACKAGE / "case-plan.json").read_text())
        original_read = Path.read_text

        def changed_read(path, *args, **kwargs):
            if path == PACKAGE / "case-plan.json":
                changed = copy.deepcopy(plan)
                changed["cases"][1]["case_id"] = changed["cases"][0]["case_id"]
                return json.dumps(changed)
            return original_read(path, *args, **kwargs)

        with patch.object(Path, "read_text", changed_read):
            with self.assertRaisesRegex(ValueError, "identities"):
                build(PACKAGE)


if __name__ == "__main__":
    unittest.main()
