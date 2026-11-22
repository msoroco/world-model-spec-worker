"""Keep authored comparisons aligned with the frozen review identities."""
import json
import hashlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT.parents[1] / "inputs" / ROOT.name / "review-context" / "review.json"


class FrozenComparisonAlignmentTest(unittest.TestCase):
    def test_exact_review_pair_ids_and_entry_order_isolation(self):
        review = json.loads(REVIEW.read_text())
        plan = json.loads((ROOT / "case-plan.json").read_text())
        planned = {item["comparison_id"]: item for item in plan["comparisons"]}
        for comparison in review["comparisons"]:
            frozen_ids = [case["case_id"] for case in comparison["cases"]]
            if len(frozen_ids) == 2:
                self.assertEqual(planned[comparison["id"]]["case_ids"], frozen_ids)
        entry = planned["crossing_entry_order"]
        self.assertEqual(entry["deliberate_differences"], ["entry_order"])
        scenes = []
        for case_id in entry["case_ids"]:
            suffix = case_id.rsplit("__", 1)[-1]
            scenes.append(json.loads((ROOT / "cases" / suffix / "scene.json").read_text()))
        self.assertEqual(scenes[0]["ego_response_request"],
                         scenes[1]["ego_response_request"])
        self.assertNotEqual(scenes[0]["other_entered_first"],
                            scenes[1]["other_entered_first"])
        self.assertEqual(scenes[0]["crossing"], scenes[1]["crossing"])
        proposals = json.loads((ROOT / "proposals" / "cases.json").read_text())
        baseline = next(item for item in proposals["cases"]
                        if item["case_id"].endswith("__precedence"))
        self.assertEqual(baseline["paired_probe_id"], "crossing_precedence")
        index = json.loads((ROOT / "proposals" / "semantic-index.json").read_text())
        self.assertEqual(index["stages"]["cases"]["sha256"],
                         hashlib.sha256((ROOT / "proposals" / "cases.json").read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
