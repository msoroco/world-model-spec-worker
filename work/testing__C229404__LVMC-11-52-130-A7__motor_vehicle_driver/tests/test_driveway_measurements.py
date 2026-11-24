import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / "driveway_measurements.py"
spec = importlib.util.spec_from_file_location("driveway_measurements", MODULE)
measurements = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = measurements
spec.loader.exec_module(measurements)


class SavedDrivewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case_id = measurements.ASSIGNMENT_ID + "__public_park_within_5ft"
        self.context = dict(case_id=self.case_id, driveway_kind="public", map_sha256="a" * 64,
                            mouth_start_xy=[0, 0], mouth_end_xy=[3, 0])
        for key in ("mouth_source", "frontage_source", "driveway_use_source",
                    "responsible_person_source", "relationship_source", "purpose_source",
                    "traffic_direction_source", "postal_status_source"):
            self.context[key] = "original:" + key
        vertices = [[x, y, z] for x in (1, 2) for y in (1, 2) for z in (0, 1)]
        self.rows = [dict(frame=i, time_s=i / 20, vehicle_vertices=vertices,
                          speed_mps=0, control_state="park") for i in range(2)]
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

    def test_plan_covers_exception_and_boundary_controls(self):
        plan = json.loads((MODULE.parent / "case-plan.json").read_text(encoding="utf-8"))
        self.assertEqual(len(plan["cases"]), 12)
        self.assertEqual(len(plan["comparisons"]), 9)
        self.assertEqual(len({c["case_id"] for c in plan["cases"]}), 12)

    def test_original_distance_is_observed_without_legal_decision(self):
        result = self.run_measure()
        self.assertAlmostEqual(result["minimum_observed_body_to_mouth_m"], 1)
        self.assertEqual(result["frontage_judgment"], "unresolved")
        self.assertEqual(result["private_relationship_judgment"], "unresolved")

    def test_diagnostic_receipt_rejected(self):
        self.receipt["diagnostic_fixture"] = True
        self.receipt_path.write_text(json.dumps(self.receipt) + "\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_mutated_trace_rejected(self):
        self.rows[0]["speed_mps"] = 2
        self.trace_path.write_text("".join(json.dumps(x) + "\n" for x in self.rows), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_wrong_cadence_rejected(self):
        self.rows[1]["time_s"] = .1
        self.write_sources()
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_missing_original_relationship_source_rejected(self):
        del self.context["relationship_source"]
        self.write_sources()
        with self.assertRaises(ValueError):
            self.run_measure()


if __name__ == "__main__":
    unittest.main()
