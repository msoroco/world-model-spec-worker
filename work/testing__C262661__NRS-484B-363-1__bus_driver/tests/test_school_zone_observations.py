import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / "school_zone_observations.py"
spec = importlib.util.spec_from_file_location("school_zone_observations", MODULE)
observations = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = observations
spec.loader.exec_module(observations)


class SchoolZoneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case_id = observations.ASSIGNMENT_ID + "__beacon_flashing_15_1"
        self.context = dict(case_id=self.case_id, map_sha256="a" * 64,
                            local_datetime="2026-11-23T08:00:00-08:00",
                            operation_end_local="2026-11-23T15:00:00-08:00",
                            next_operation_start_local="2026-11-24T07:30:00-08:00",
                            class_start_local="2026-11-23T07:45:00-08:00",
                            class_end_local="2026-11-23T14:45:00-08:00",
                            school_in_session_today=True, operational_beacon_designation=True)
        for key in ("zone_designation_source", "zone_boundaries_source", "school_property_source",
                    "bus_route_source", "bus_blueprint_source", "driver_identity_source", "children_locations_source",
                    "civil_date_time_source", "school_calendar_source", "operation_hours_source",
                    "class_hours_source", "beacon_designation_source", "beacon_operability_source",
                    "beacon_lamp_configuration_source", "beacon_lamp_history_source", "sign_active_period_source"):
            self.context[key] = "original:" + key
        self.rows = [dict(frame=i, time_s=i / 20, bus_speed_mps=6.75,
                          inside_designated_zone=True, beacon_yellow_lights_lit=[i == 0, i == 1],
                          sign_limit_active=True, children_actor_ids=["child-1"]) for i in range(2)]
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

    def test_exact_speed_exception_plan(self):
        plan = json.loads((MODULE.parent / "case-plan.json").read_text(encoding="utf-8"))
        self.assertEqual(len(plan["cases"]), 15)
        self.assertEqual(len(plan["comparisons"]), 12)
        self.assertEqual(len({x["case_id"] for x in plan["cases"]}), 15)

    def test_original_speed_beacon_and_children_kept_separate(self):
        result = self.run_measure()
        self.assertGreater(result["maximum_observed_inside_zone_mph"], 15)
        self.assertEqual(result["observations"][0]["beacon_yellow_lights_lit"], [True, False])
        self.assertEqual(result["observations"][0]["children_actor_ids"], ["child-1"])
        self.assertEqual(result["exception_judgment"], "unresolved")

    def test_diagnostic_receipt_rejected(self):
        self.receipt["diagnostic_fixture"] = True
        self.receipt_path.write_text(json.dumps(self.receipt) + "\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_changed_trace_rejected(self):
        self.rows[0]["bus_speed_mps"] = 2
        self.trace_path.write_text("".join(json.dumps(x) + "\n" for x in self.rows), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_nonboolean_zone_membership_rejected(self):
        self.rows[0]["inside_designated_zone"] = 1
        self.write_sources()
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_missing_calendar_source_rejected(self):
        del self.context["school_calendar_source"]
        self.write_sources()
        with self.assertRaises(ValueError):
            self.run_measure()

    def test_missing_yellow_lamp_states_rejected(self):
        del self.rows[0]["beacon_yellow_lights_lit"]
        self.write_sources()
        with self.assertRaises(ValueError):
            self.run_measure()


if __name__ == "__main__":
    unittest.main()
