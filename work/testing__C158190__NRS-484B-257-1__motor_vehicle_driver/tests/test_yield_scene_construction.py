import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from yield_scene_construction import VARIANTS, construct
from yield_view_measurement import ASSIGNMENT


class Adapter:
    def __init__(self):
        self.calls = []
        self.control = None
        self.stop_line = False

    def read_control(self, approach):
        self.calls.append("read_control")
        return self.control

    def spawn_yield_sign(self, blueprint, transform):
        self.calls.append("spawn_yield_sign")
        return "sign-fixture"

    def read_sign(self, sign_id):
        self.calls.append("read_sign")
        return {"control": "yield_sign", "governed_approach_id": "approach-fixture"}

    def survey_markings(self, approach):
        self.calls.append("survey_markings")
        return {"stop_line_present": self.stop_line, "near_crosswalk_present": False,
                "sidewalk_derived_crosswalk_present": False}

    def survey_view_stations(self, approach):
        self.calls.append("survey_view_stations")
        return [{"station_id": "view-fixture", "view_of_through_traffic": True}]

    def spawn_through_vehicle(self, plan, delay):
        self.calls.append("spawn_through_vehicle")
        return "vehicle-fixture"


class ConstructionTests(unittest.TestCase):
    def packet(self):
        digest = "a" * 64
        return {"assignment_id": ASSIGNMENT, "cell_id": "C158190",
                "review_status": "reviewed", "source_kind": "original_site_survey",
                "approved_control_variant": "yield_sign",
                "map_source_sha256": digest, "yield_sign_survey_sha256": digest,
                "marking_survey_sha256": digest, "view_ray_survey_sha256": digest,
                "through_highway_survey_sha256": digest,
                "police_control_active": False, "traffic_signal_control_active": False,
                "stop_line_present": False, "near_crosswalk_present": False,
                "sidewalk_derived_crosswalk_present": False,
                "yield_sign": {"blueprint_id": "yield-fixture",
                               "governed_approach_id": "approach-fixture",
                               "transform": {"x": 1, "y": 2, "z": 3, "yaw": 4}},
                "through_vehicle": {"route_source_id": "route-fixture"},
                "case_plans": {name: {"ego_response": response,
                                      "through_traffic_phase": phase,
                                      "through_start_delay_s": 0.5}
                               for name, (response, phase) in VARIANTS.items()}}

    def run_build(self, packet, adapter, suffix="yield_slow_hazard"):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as directory:
            path = Path(directory) / "site.json"
            path.write_text(json.dumps(packet), encoding="utf-8")
            return construct(adapter, path, ASSIGNMENT + "__" + suffix)

    def test_all_three_variants_issue_native_calls(self):
        for suffix in VARIANTS:
            with self.subTest(suffix=suffix):
                adapter = Adapter()
                result = self.run_build(self.packet(), adapter, suffix)
                self.assertEqual(result["planned_response"], VARIANTS[suffix][0])
                self.assertEqual(adapter.calls, ["read_control", "spawn_yield_sign", "read_sign",
                                                 "survey_markings", "survey_view_stations",
                                                 "spawn_through_vehicle"])

    def test_active_stop_sign_rejected_before_spawn(self):
        adapter = Adapter()
        adapter.control = "stop_sign"
        with self.assertRaisesRegex(ValueError, "active stop sign"):
            self.run_build(self.packet(), adapter)
        self.assertEqual(adapter.calls, ["read_control"])

    def test_missing_variant_review_rejected(self):
        packet = self.packet()
        packet["approved_control_variant"] = None
        with self.assertRaisesRegex(ValueError, "reviewed yield control variant"):
            self.run_build(packet, Adapter())

    def test_native_marking_conflict_rejected(self):
        adapter = Adapter()
        adapter.stop_line = True
        with self.assertRaisesRegex(ValueError, "marking readback"):
            self.run_build(self.packet(), adapter)


if __name__ == "__main__":
    unittest.main()
