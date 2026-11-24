import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / "turn_lane_observations.py"
spec = importlib.util.spec_from_file_location("turn_lane_observations", MODULE)
observations = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = observations
spec.loader.exec_module(observations)


class TurnLaneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case_id = observations.ASSIGNMENT_ID + "__exclusive_right_through_blind"
        self.context = dict(case_id=self.case_id, map_sha256="a" * 64,
                            approach_lane_ids=["right_turn", "through"], right_turn_lane_id="right_turn",
                            intersection_entry_station_m=10, intersection_exit_station_m=20,
                            intersection_type="non_alley", lane_design="exclusive_single_right",
                            independent_route_intent="through")
        for key in ("public_highway_source", "roadway_boundary_source", "lane_design_source",
                    "exclusive_turn_control_source", "intersection_type_source", "intersection_boundary_source",
                    "straight_route_source", "right_turn_route_source", "sightline_obstruction_source",
                    "driver_identity_source", "motor_vehicle_source", "independent_route_intent_source"):
            self.context[key] = "original:" + key
        self.rows = [dict(frame=i, time_s=i / 20, lane_id="right_turn", speed_mps=5,
                          ego_station_m=station, connected_route="through")
                     for i, station in enumerate((9, 15, 21))]
        self.write_sources()

    def write_sources(self):
        self.context_path = self.root / "context.json"
        self.trace_path = self.root / "trace.jsonl"
        self.receipt_path = self.root / "receipt.json"
        self.context_path.write_text(json.dumps(self.context) + "\n", encoding="utf-8")
        self.trace_path.write_text("".join(json.dumps(x) + "\n" for x in self.rows), encoding="utf-8")
        self.receipt = dict(assignment_id=observations.ASSIGNMENT_ID, case_id=self.case_id,
                            source_kind="original_native_capture", diagnostic_fixture=False,
                            context_sha256=observations.sha(self.context_path),
                            trace_sha256=observations.sha(self.trace_path), fps=20, frame_count=3)
        self.receipt_path.write_text(json.dumps(self.receipt) + "\n", encoding="utf-8")

    def run_measure(self):
        return observations.measure(self.case_id, self.context_path, self.trace_path, self.receipt_path)

    def test_exact_lane_and_junction_plan(self):
        plan = json.loads((MODULE.parent / "case-plan.json").read_text(encoding="utf-8"))
        self.assertEqual(len(plan["cases"]), 9)
        self.assertEqual(len(plan["comparisons"]), 8)
        self.assertEqual(len({x["case_id"] for x in plan["cases"]}), 9)

    def test_original_lane_and_interval_observed_without_legal_inference(self):
        result = self.run_measure()
        self.assertEqual(result["first_interval_frame"], 1)
        self.assertEqual(result["first_beyond_exit_frame"], 2)
        self.assertEqual(result["lane_at_first_interval_frame"], "right_turn")
        self.assertEqual(result["travel_through_judgment"], "unresolved")

    def test_diagnostic_receipt_rejected(self):
        self.receipt["diagnostic_fixture"] = True
        self.receipt_path.write_text(json.dumps(self.receipt) + "\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_changed_trace_rejected(self):
        self.rows[0]["speed_mps"] = 2
        self.trace_path.write_text("".join(json.dumps(x) + "\n" for x in self.rows), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_missing_turn_lane_rejected(self):
        self.context["right_turn_lane_id"] = "missing"
        self.write_sources()
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_bad_intersection_bounds_rejected(self):
        self.context["intersection_exit_station_m"] = 10
        self.write_sources()
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_bad_approach_start_rejected(self):
        self.rows[0]["ego_station_m"] = 10
        self.write_sources()
        with self.assertRaises(ValueError):
            self.run_measure()


if __name__ == "__main__":
    unittest.main()
