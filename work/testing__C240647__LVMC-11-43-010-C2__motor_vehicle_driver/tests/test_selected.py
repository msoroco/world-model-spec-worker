"""Selected right-lane/intent/exit source-gate tests."""
import importlib.util
import json
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parents[1]

def module(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+".py"))
    value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

route=module("roundabout")
native=module("native_capture")
plan=json.loads((HERE/"case-plan.json").read_text())

class SelectedSourceTests(unittest.TestCase):
    def packets(self,case):
        name=case["case_id"].removeprefix(HERE.name+"__")
        folder=HERE/"cases"/name/"diagnostic-sources"
        return (json.loads((folder/"map.json").read_text()),
                json.loads((folder/"history.json").read_text()))

    def test_nine_exact_controls_have_source_mapped_routes_and_observed_values(self):
        self.assertEqual(len(plan["cases"]),9)
        self.assertEqual(len(plan["comparisons"]),8)
        for case in plan["cases"]:
            source,history=self.packets(case)
            topo=route.verify_topology(source,case)
            values=route.verify_original_history(history,topo,case["case_id"],9)
            self.assertEqual(values["operator_intended_exit_role"],case["operator_intent_request"])
            self.assertEqual(values["first_observed_exit_connector_id"],
                None if case["actual_exit_request"]=="no_exit" else
                "connector-"+case["actual_exit_request"])

    def test_unmapped_right_lane_and_unreviewed_intent_rejected(self):
        case=plan["cases"][0]
        source,history=self.packets(case)
        source["lanes"]["right"].pop("source_waypoint_ids")
        with self.assertRaisesRegex(ValueError,"source lane provenance"):
            route.verify_topology(source,case)
        source,_=self.packets(case)
        topo=route.verify_topology(source,case)
        history["operator_intended_exit_role"]="through"
        with self.assertRaisesRegex(ValueError,"independent intent"):
            route.verify_original_history(history,topo,case["case_id"],9)

    def test_review_intent_must_preexist_motion(self):
        case=plan["cases"][0]
        review={"source_kind":"reviewed_original_native_roundabout",
                "assignment_id":HERE.name,"cell_id":"C240647",
                "jurisdiction":"Las Vegas, Nevada",
                "independent_operator_intent":{"case_id":case["case_id"],
                    "requested_exit_role":"through","source_sha256":"a"*64},
                "entry_id":"e","exit_id":"x","vehicle_blueprint":"vehicle.fixture",
                "map_sha256":"a"*64,"controller_sha256":"b"*64,
                "weather_sha256":"c"*64,"camera_plan_sha256":"d"*64,
                "case_ids":[row["case_id"] for row in plan["cases"]]}
        with self.assertRaisesRegex(ValueError,"independent source-bound operator intention"):
            native._validate_review(review,case)

if __name__=="__main__":
    unittest.main()
