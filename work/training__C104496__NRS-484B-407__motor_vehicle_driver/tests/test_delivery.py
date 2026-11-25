"""Focused CPU checks of selected source binding and independent rejection."""
import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class DeliveryTests(unittest.TestCase):
    def test_selected_case_and_camera_plan(self):
        plan = json.loads((HERE / "case-plan.json").read_text())
        config = json.loads((HERE / "config.json").read_text())
        selected = {row["case_id"] for row in plan["cases"]}
        self.assertEqual(set(config["supported_case_ids"]), selected)
        self.assertEqual([row["name"] for row in config["cameras"]],
                         ["overview", "approach", "reference_corner", "driver_reference"])
        self.assertEqual(plan["camera_plan"]["duration_s"], config["duration_s"])
        self.assertEqual(set(plan["source_observation_mapping"]),
                         {"drv.u_turn", "st.curvature", "st.grade", "st.sight_distance", "rel.oncoming", "drv.approaching", "kin.position"})

    def test_original_source_required(self):
        auditor = module("delivery_audit")
        case = HERE.name + "__probe_01"
        result = {"case_id": case, "provenance_kind": "synthetic_fixture",
                  "diagnostic_fixture": True, "maneuver_completed": True}
        with self.assertRaisesRegex(ValueError, "Missing original source"):
            auditor.check_result(result, case)

    def test_comparison_rejects_changed_fixed_camera(self):
        auditor = module("comparison_audit")
        left = auditor.config_from_construction("probe_01")
        right = auditor.config_from_construction("probe_03")
        auditor.check("curvature_comparison", left, right)
        right["camera_policy"] = "changed"
        with self.assertRaisesRegex(ValueError, "Fixed condition changed"):
            auditor.check("curvature_comparison", left, right)


if __name__ == "__main__":
    unittest.main()
