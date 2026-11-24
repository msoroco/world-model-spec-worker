import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / "parking_measurements.py"
spec = importlib.util.spec_from_file_location("parking_measurements", MODULE)
measurements = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = measurements
spec.loader.exec_module(measurements)


class ParkingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case_id = measurements.ASSIGNMENT_ID + "__left_park_official_permit"
        self.context = dict(case_id=self.case_id, map_sha256="a" * 64,
                            road_origin_xy=[0, 0], road_forward_xy=[1, 0],
                            marked_lane_count=2, one_way_restriction=True,
                            device_kind="official_park_permit")
        for key in ("roadway_public_use_source", "roadway_boundary_source", "marked_lanes_source",
                    "direction_restriction_source", "device_inventory_source", "device_erection_source",
                    "device_official_status_source", "device_instruction_source",
                    "device_governed_space_source", "parking_person_source", "halt_purpose_source"):
            self.context[key] = "original:" + key
        vertices = [[x, y, z] for x in (1, 2) for y in (3, 4) for z in (0, 1)]
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

    def test_exact_plan_controls(self):
        plan = json.loads((MODULE.parent / "case-plan.json").read_text(encoding="utf-8"))
        self.assertEqual(len(plan["cases"]), 12)
        self.assertEqual(len(plan["comparisons"]), 10)
        self.assertEqual(len({x["case_id"] for x in plan["cases"]}), 12)

    def test_original_leftward_body_is_measured_without_permission_inference(self):
        result = self.run_measure()
        self.assertEqual((result["observations"][0]["leftward_min_m"],
                          result["observations"][0]["leftward_max_m"]), (3, 4))
        self.assertEqual(result["device_permission_judgment"], "unresolved")

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

    def test_missing_device_source_rejected(self):
        del self.context["device_official_status_source"]
        self.write_sources()
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_non_unit_road_direction_rejected(self):
        self.context["road_forward_xy"] = [2, 0]
        self.write_sources()
        with self.assertRaises(ValueError):
            self.run_measure()


if __name__ == "__main__":
    unittest.main()
