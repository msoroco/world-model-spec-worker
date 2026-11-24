import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / "lamp_observations.py"
spec = importlib.util.spec_from_file_location("lamp_observations", MODULE)
observations = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = observations
spec.loader.exec_module(observations)


class LampTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case_id = observations.ASSIGNMENT_ID + "__night_moving_both_lit"
        self.context = dict(case_id=self.case_id, map_sha256="a" * 64,
                            local_datetime="2026-11-23T19:00:00-08:00",
                            sunset_local="2026-11-23T16:30:00-08:00",
                            sunrise_local="2026-11-24T06:30:00-08:00",
                            observed_discernibility_ft=450,
                            headlamp_calibration=dict(emitted_color="white", mounted_position="front",
                                                      tested_visibility_ft=300),
                            tail_lamp_calibration=dict(emitted_color="red", mounted_position="rear",
                                                       tested_visibility_ft=500))
        for key in ("vehicle_blueprint_source", "section_080_coverage_source", "trail_ride_source",
                    "enclosed_three_wheel_source", "road_sidewalk_source", "local_date_time_source",
                    "sunset_sunrise_source", "light_atmosphere_source", "discernibility_500ft_source",
                    "headlamp_calibration_source", "tail_lamp_calibration_source"):
            self.context[key] = "original:" + key
        self.rows = [dict(frame=i, time_s=i / 20, speed_mps=5,
                          headlamp_burning=True, tail_lamp_burning=True) for i in range(2)]
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
                            trace_sha256=observations.sha(self.trace_path), fps=20, frame_count=2)
        self.receipt_path.write_text(json.dumps(self.receipt) + "\n", encoding="utf-8")

    def run_measure(self):
        return observations.measure(self.case_id, self.context_path, self.trace_path, self.receipt_path)

    def test_exact_lamp_and_coverage_plan(self):
        plan = json.loads((MODULE.parent / "case-plan.json").read_text(encoding="utf-8"))
        self.assertEqual(len(plan["cases"]), 17)
        self.assertEqual(len(plan["comparisons"]), 14)
        self.assertEqual(len({x["case_id"] for x in plan["cases"]}), 17)

    def test_original_lamp_states_and_calibration_preserved(self):
        result = self.run_measure()
        self.assertEqual(result["calibrated_headlamp"]["tested_visibility_ft"], 300)
        self.assertEqual(result["observed_discernibility_ft"], 450)
        self.assertTrue(result["observations"][0]["tail_lamp_burning"])
        self.assertEqual(result["visibility_judgment"], "unresolved")

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

    def test_missing_calibration_rejected(self):
        del self.context["headlamp_calibration_source"]
        self.write_sources()
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_wrong_tail_mount_rejected(self):
        self.context["tail_lamp_calibration"]["mounted_position"] = "front"
        self.write_sources()
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_nonboolean_lamp_state_rejected(self):
        self.rows[0]["headlamp_burning"] = 1
        self.write_sources()
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_missing_discernibility_measurement_rejected(self):
        del self.context["observed_discernibility_ft"]
        self.write_sources()
        with self.assertRaises(ValueError):
            self.run_measure()


if __name__ == "__main__":
    unittest.main()
