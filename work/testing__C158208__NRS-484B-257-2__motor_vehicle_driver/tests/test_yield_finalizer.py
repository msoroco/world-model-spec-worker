import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from finalizer import MEASUREMENT_INPUTS, bound_measurements, build_result, finalize
from yield_stage import KINDS, PREFIX


class FinalizerTests(unittest.TestCase):
    def report(self):
        return {"first_ego_entry": {"frame": 102, "time_s": 5.1},
                "observed_slowed_or_stopped_before_reference": True,
                "other_inside_at_ego_entry": True,
                "other_not_obligated_by_stop_or_yield": True,
                "officer_control_observed": False,
                "sources": {"entry_history.jsonl": "fixture-hash"},
                "samples": [{"frame": 100, "time_s": 5.0, "ego_speed_mps": 4,
                             "ego_body_in_intersection": False,
                             "other_body_in_intersection": True,
                             "other_distance_to_intersection_center_m": 3,
                             "other_center_closing_mps": None,
                             "ego_body_before_yield_reference": True},
                            {"frame": 102, "time_s": 5.1, "ego_speed_mps": 2,
                             "ego_body_in_intersection": True,
                             "other_body_in_intersection": True,
                             "other_distance_to_intersection_center_m": 2,
                             "other_center_closing_mps": 10,
                             "ego_body_before_yield_reference": False}]}

    def test_exact_targets_use_observed_sources_without_legal_cutoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt = Path(tmp)
            (attempt / "capture").mkdir()
            (attempt / "capture/evidence.jsonl").write_text("source fixture\n")
            config = json.loads((ROOT / "config.json").read_text())
            expected = {"yield_other_inside": True, "yield_other_approaching": True,
                        "yield_other_obligated": False, "yield_no_slow": False,
                        "officer_control_exception": False}
            for kind in KINDS:
                result, channels = build_result(attempt,
                    dict(config, selected_case_id=PREFIX + kind), self.report())
                self.assertEqual(result["target_checks"][0]["matched"], expected[kind])
                self.assertFalse(result["target_checks"][0]["physical_cause_confirmed"])
                self.assertIn("other_center_closing_mps", channels)
                self.assertNotIn("legal_verdict", result)

    def test_missing_original_sources_rejected_before_any_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt = Path(tmp)
            with self.assertRaisesRegex(ValueError, "Missing required source: config.json"):
                finalize(attempt, attempt / "analysis.json")
            self.assertFalse((attempt / "result.json").exists())

    def test_each_selected_requirement_has_source_bound_value(self):
        report = self.report()
        report.update(non_through_highway=True, native_yield_sign_id=17,
                      subsection_one_reference={"reference_kind": "nearest_view_point"},
                      other_entrance_device="none", officer_control_source_sha256=None)
        report["sources"] = {name: "sha-" + name
                             for names in MEASUREMENT_INPUTS.values() for name in names}
        values = bound_measurements(report)
        self.assertEqual(set(values), set(MEASUREMENT_INPUTS))
        for key, item in values.items():
            self.assertTrue(item["method"].startswith("measure_"))
            self.assertEqual(set(item["sources"]), set(MEASUREMENT_INPUTS[key]))
            self.assertTrue(item["value"])
        self.assertEqual(values["signed_entrance"]["value"]["yield_sign_id"], 17)
        self.assertEqual(values["other_crossing_relation"]["value"]["samples"][1]["closing_mps"], 10)


if __name__ == "__main__":
    unittest.main()
