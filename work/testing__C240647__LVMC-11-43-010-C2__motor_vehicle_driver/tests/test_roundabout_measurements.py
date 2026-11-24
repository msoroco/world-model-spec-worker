import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / "roundabout_measurements.py"
spec = importlib.util.spec_from_file_location("roundabout_measurements", MODULE)
measurements = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = measurements
spec.loader.exec_module(measurements)


class RoundaboutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case_id = measurements.ASSIGNMENT_ID + "__right_intent_right_lane"
        self.context = dict(case_id=self.case_id, map_sha256="a" * 64,
                            circulating_lane_ids=["right", "left"], right_lane_id="right",
                            right_exit_connector_id="right_exit", through_exit_connector_id="through_exit",
                            operator_intended_exit_id="right_exit")
        for key in ("jurisdiction_source", "roundabout_graph_source", "right_lane_source",
                    "right_exit_connector_source", "operator_identity_source", "operator_intent_source",
                    "independent_route_source", "vehicle_class_source"):
            self.context[key] = "original:" + key
        self.rows = [dict(frame=0, time_s=0, section="circulating", lane_id="right",
                          exit_connector_id=None, speed_mps=4),
                     dict(frame=1, time_s=.05, section="exit", lane_id="exit_lane",
                          exit_connector_id="right_exit", speed_mps=4)]
        self.write_sources()

    def write_sources(self):
        self.context_path = self.root / "context.json"
        self.trace_path = self.root / "trace.jsonl"
        self.receipt_path = self.root / "receipt.json"
        self.context_path.write_text(json.dumps(self.context) + "\n", encoding="utf-8")
        self.trace_path.write_text("".join(json.dumps(x) + "\n" for x in self.rows), encoding="utf-8")
        self.receipt = dict(assignment_id=measurements.ASSIGNMENT_ID, case_id=self.case_id,
                            source_kind="original_native_capture", diagnostic_fixture=False,
                            context_sha256=measurements.sha(self.context_path),
                            trace_sha256=measurements.sha(self.trace_path), fps=20, frame_count=2)
        self.receipt_path.write_text(json.dumps(self.receipt) + "\n", encoding="utf-8")

    def run_measure(self):
        return measurements.measure(self.case_id, self.context_path, self.trace_path, self.receipt_path)

    def test_exact_intent_lane_and_exit_plan(self):
        plan = json.loads((MODULE.parent / "case-plan.json").read_text(encoding="utf-8"))
        self.assertEqual(len(plan["cases"]), 9)
        self.assertEqual(len(plan["comparisons"]), 8)
        self.assertEqual(len({x["case_id"] for x in plan["cases"]}), 9)

    def test_independent_intent_and_actual_exit_preserved(self):
        result = self.run_measure()
        self.assertEqual(result["operator_intended_exit_id"], "right_exit")
        self.assertEqual(result["first_observed_exit_connector_id"], "right_exit")
        self.assertEqual(result["last_circulating_lane_id"], "right")
        self.assertEqual(result["right_lane_use_judgment"], "unresolved")

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

    def test_bad_lane_graph_rejected(self):
        self.context["right_lane_id"] = "missing"
        self.write_sources()
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_missing_intent_rejected(self):
        del self.context["operator_intended_exit_id"]
        self.write_sources()
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_unknown_connector_rejected(self):
        self.rows[1]["exit_connector_id"] = "unknown"
        self.write_sources()
        with self.assertRaises(ValueError):
            self.run_measure()


if __name__ == "__main__":
    unittest.main()
