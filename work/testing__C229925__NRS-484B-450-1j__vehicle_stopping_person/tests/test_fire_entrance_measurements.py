import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import os


MODULE = Path(__file__).resolve().parents[1] / "fire_entrance_measurements.py"
spec = importlib.util.spec_from_file_location("fire_entrance_measurements", MODULE)
measurements = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = measurements
spec.loader.exec_module(measurements)


class FireEntranceTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ.get("TMPDIR", ".runtime-work/c229925-tests"))
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case_id = measurements.ASSIGNMENT_ID + "__opposite_stop_74ft"
        self.context = dict(case_id=self.case_id, map_sha256="a" * 64,
                            entrance_start_xy=[0, 4], entrance_end_xy=[3, 4],
                            road_origin_xy=[0, 0], road_forward_xy=[1, 0])
        for key in ("station_identity_source", "entrance_boundary_source", "highway_boundary_source",
                    "highway_dedication_source", "public_vehicular_use_source", "entrance_side_source",
                    "stopping_person_source", "halt_purpose_source", "traffic_conflict_source",
                    "law_direction_source", "police_direction_source", "official_device_direction_source"):
            self.context[key] = "original:" + key
        vertices = [[x, y, z] for x in (1, 2) for y in (-4, -3) for z in (0, 1)]
        self.rows = [dict(frame=i, time_s=i / 20, vehicle_vertices=vertices,
                          speed_mps=0, control_state="stop") for i in range(2)]
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

    def test_exact_boundary_and_exception_plan(self):
        plan = json.loads((MODULE.parent / "case-plan.json").read_text(encoding="utf-8"))
        self.assertEqual(len(plan["cases"]), 15)
        self.assertEqual(len(plan["comparisons"]), 13)
        self.assertEqual(len({x["case_id"] for x in plan["cases"]}), 15)

    def test_original_opposite_geometry_keeps_legal_judgment_open(self):
        result = self.run_measure()
        self.assertEqual(result["entrance_lateral_m"], 4)
        self.assertEqual(result["observations"][0]["vehicle_lateral_max_m"], -3)
        self.assertEqual(result["minimum_observed_vertex_to_entrance_m"], 7)
        self.assertEqual(result["opposite_highway_side_judgment"], "unresolved")

    def test_diagnostic_receipt_rejected(self):
        self.receipt["diagnostic_fixture"] = True
        self.receipt_path.write_text(json.dumps(self.receipt) + "\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_changed_trace_rejected(self):
        self.rows[0]["speed_mps"] = 1
        self.trace_path.write_text("".join(json.dumps(x) + "\n" for x in self.rows), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_bad_cadence_rejected(self):
        self.rows[1]["time_s"] = .1
        self.write_sources()
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_original_frame_offset_supported(self):
        for row in self.rows:
            row["frame"] += 100
            row["time_s"] += 230.0
        self.write_sources()
        result = self.run_measure()
        self.assertEqual(result["observations"][0]["frame"], 100)

    def test_missing_station_identity_rejected(self):
        del self.context["station_identity_source"]
        self.write_sources()
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_ambiguous_entrance_side_rejected(self):
        self.context["entrance_start_xy"] = [0, 0]
        self.context["entrance_end_xy"] = [3, 0]
        self.write_sources()
        with self.assertRaises(ValueError):
            self.run_measure()


if __name__ == "__main__":
    unittest.main()
