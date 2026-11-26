import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_audit import CASES, COMPARISONS, audit
from parking_place import ASSIGNMENT, construct, measure
from test_parking_place import ParkingPlaceTests


class ComparisonAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def sources(self, comparison):
        paths = {}
        for name in COMPARISONS[comparison]:
            conduct, footprint, context = CASES[name]
            site = ParkingPlaceTests().site()
            site["hazard_or_congestion_status"] = context
            candidate = "inside" if footprint == "inside" else "outside"
            site_path = self.root / (name + "-site.json")
            site_path.write_text(json.dumps(site), encoding="utf-8")
            construction = construct(site_path, candidate)
            trace = ParkingPlaceTests().packet()
            trace["hazard_or_congestion_status"] = context
            trace["original_trace_id"] = "original-" + name
            if footprint == "outside":
                trace["frames"] = [dict(frame, vehicle_footprint=[
                    [11, 1.5], [15, 1.5], [15, 3.5], [11, 3.5]]) for frame in trace["frames"]]
            trace_path = self.root / (name + "-trace.json")
            trace_path.write_text(json.dumps(trace), encoding="utf-8")
            measurement = measure(trace_path)
            packet = {"assignment_id": ASSIGNMENT, "case_id": ASSIGNMENT + "__" + name,
                      "requested_conduct": conduct, "requested_footprint": footprint,
                      "place_context_for_review": context, "construction": construction,
                      "measurement": measurement, "vehicle_blueprint": "synthetic-car",
                      "device_id": "device-a", "designated_place_id": "zone-a",
                      "camera_plan_sha256": "synthetic-cameras", "duration_s": 10,
                      "rate_hz": 20, "parking_pose_sha256": "pose-inside" if footprint == "inside" else "pose-outside",
                      "conduct_source_sha256": "conduct-" + conduct,
                      "place_context_source_sha256": "context-" + context}
            path = self.root / (name + ".json")
            path.write_text(json.dumps(packet), encoding="utf-8")
            paths[name] = path
        return paths

    def rewrite(self, path, update):
        value = json.loads(path.read_text(encoding="utf-8"))
        update(value)
        path.write_text(json.dumps(value), encoding="utf-8")

    def test_all_planned_comparisons(self):
        for comparison in COMPARISONS:
            with self.subTest(comparison=comparison):
                self.assertTrue(audit(comparison, self.sources(comparison))["passed"])

    def test_missing_evidence_rejected(self):
        paths = self.sources("inside_vs_outside")
        paths.pop("park_outside_hazard")
        with self.assertRaisesRegex(ValueError, "missing"):
            audit("inside_vs_outside", paths)

    def test_wrong_fixed_device_rejected(self):
        paths = self.sources("inside_vs_outside")
        path = paths["park_outside_hazard"]
        self.rewrite(path, lambda p: p.update(device_id="different-device"))
        with self.assertRaisesRegex(ValueError, "fixed comparison"):
            audit("inside_vs_outside", paths)

    def test_missing_outside_footprint_rejected(self):
        paths = self.sources("inside_vs_outside")
        path = paths["park_outside_hazard"]
        self.rewrite(path, lambda p: [o.update(body_wholly_outside_place=False)
                                      for o in p["measurement"]["observations"]])
        with self.assertRaisesRegex(ValueError, "outside body"):
            audit("inside_vs_outside", paths)

    def test_missing_separate_context_rejected(self):
        paths = self.sources("hazard_vs_congestion")
        path = paths["park_inside_congested"]
        self.rewrite(path, lambda p: p.update(place_context_source_sha256="context-hazardous"))
        with self.assertRaisesRegex(ValueError, "separate place"):
            audit("hazard_vs_congestion", paths)


if __name__ == "__main__":
    unittest.main()
