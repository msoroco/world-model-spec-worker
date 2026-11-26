import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CaseProposalTests(unittest.TestCase):
    def test_nine_exact_cases_and_seven_comparisons(self):
        plan = json.loads((ROOT / "case-plan.json").read_text())
        proposal = json.loads((ROOT / "proposals" / "cases.json").read_text())
        selected = {case["case_id"]: case for case in proposal["cases"]
                    if case["target_type"] != "baseline"}
        self.assertEqual(set(selected), {case["case_id"] for case in plan["cases"]})
        self.assertEqual(len(plan["comparisons"]), 7)
        for case in plan["cases"]:
            assignments = selected[case["case_id"]]["variable_assignments"]
            self.assertEqual(assignments["entry_request"]["value"], case["entry_request"])
            self.assertEqual(assignments["other_device_indication"]["value"],
                             case["other_device_indication"])
            judgments = selected[case["case_id"]]["unresolved_judgment_calls"]
            self.assertTrue(any((item.get("phrase") if isinstance(item, dict) else item)
                                == "unless permitted to proceed by another device as provided in NRS 484B.283"
                                for item in judgments))
        for comparison in plan["comparisons"]:
            self.assertTrue(set(comparison["case_ids"]) <= set(selected))

    def test_declared_channels_are_supported_by_saved_finalizer(self):
        proposal = json.loads((ROOT / "proposals" / "cases.json").read_text())
        supported = {"walker_body_history", "facing_signal_history",
                     "other_device_history", "camera_frame_map"}
        for case in proposal["cases"]:
            description = case["recording_description"]
            expected = supported | ({"original_pedestrian_speed_mps"} if case.get("sweep_id") else set())
            self.assertEqual({item["name"] for item in description["channels"]}, expected)
            self.assertEqual([item["name"] for item in description["context_inputs"]],
                             ["highway_boundary"])
            self.assertTrue(all(item["sampling_rate_hz"] == 20
                                for item in description["channels"]))


if __name__ == "__main__":
    unittest.main()
