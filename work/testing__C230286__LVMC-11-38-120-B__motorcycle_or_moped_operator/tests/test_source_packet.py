import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "source_packet.py"
spec = importlib.util.spec_from_file_location("c230286_source_packet", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.path.insert(0, str(SOURCE.parent))
import lamp_controls
import pair_audit


class SourcePacketTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.packet = self.root / "source-packet.json"
        refs = {}
        for name in module.SOURCE_NAMES:
            path = self.root / (name + ".txt")
            path.write_text("diagnostic source for " + name + "\n", encoding="utf-8")
            refs[name] = {"path": path.name, "sha256": module.sha(path),
                          "reviewed_by": "CPU fixture", "method": "fixture only"}
        self.data = {"assignment_id": module.ASSIGNMENT,
                     "case_id": module.ASSIGNMENT + "__night_moving_both_lit",
                     "source_kind": "diagnostic_fixture", "source_refs": refs,
                     "scene": {"cell_id": "C230286", "law_id": "LVMC-11-38-120-B",
                               "actor": "motorcycle_or_moped_operator", "map_name": "fixture-map",
                               "vehicle_blueprint": "fixture-motorcycle",
                               "route": {"surface": "roadway", "sidewalk_relation": "adjacent_separate",
                                         "waypoints": [[0, 0], [10, 0]]},
                               "sidewalk": {"surface": "sidewalk", "polygon": [[0, 2], [10, 2], [10, 3]]},
                               "local_datetime": "2026-11-23T19:00:00-08:00",
                               "sunset_local": "2026-11-23T16:30:00-08:00",
                               "sunrise_local": "2026-11-24T06:30:00-08:00",
                               "coverage_request": "covered_motorcycle", "illumination_request": "night",
                               "motion_request": "moving", "lit_state_request": "both_lit",
                               "timing_request": "night", "discernibility_request_ft": 450,
                               "calibrated_lamp_request": "white_300_red_500",
                               "duration_s": 12, "rate_hz": 20, "requested_speed_mps": 5}}
        astronomical = self.root / "astronomical_times.txt"
        astronomical.write_text(json.dumps({key: self.data["scene"][key] for key in
                                            ("local_datetime", "sunset_local", "sunrise_local")}) + "\n",
                                encoding="utf-8")
        refs["astronomical_times"]["sha256"] = module.sha(astronomical)
        self.save()

    def save(self):
        self.packet.write_text(json.dumps(self.data, sort_keys=True) + "\n", encoding="utf-8")

    def test_exact_diagnostic_source_contract(self):
        result = module.verify(self.packet, diagnostic_fixture=True)
        self.assertEqual(result["physical_acceptance"], "unverified")
        self.assertEqual(result["requested_controls"]["motion_request"], "moving")

    def test_fixture_cannot_claim_original_review(self):
        with self.assertRaisesRegex(ValueError, "reviewed original"):
            module.verify(self.packet)

    def test_missing_photometry_source_rejected(self):
        (self.root / "tail_lamp_photometry.txt").unlink()
        with self.assertRaisesRegex(ValueError, "tail_lamp_photometry"):
            module.verify(self.packet, diagnostic_fixture=True)

    def test_changed_map_source_rejected(self):
        (self.root / "map_opendrive.txt").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "map_opendrive"):
            module.verify(self.packet, diagnostic_fixture=True)

    def test_sidewalk_must_remain_separate(self):
        self.data["scene"]["route"]["surface"] = "sidewalk"
        self.save()
        with self.assertRaisesRegex(ValueError, "separate sidewalk"):
            module.verify(self.packet, diagnostic_fixture=True)

    def test_source_paths_cannot_escape_packet(self):
        self.data["source_refs"]["map_opendrive"]["path"] = "../map.xodr"
        self.save()
        with self.assertRaisesRegex(ValueError, "sibling file"):
            module.verify(self.packet, diagnostic_fixture=True)

    def test_no_photometry_request_outside_reviewed_controls(self):
        self.data["scene"]["calibrated_lamp_request"] = "white_999_red_999"
        self.save()
        with self.assertRaisesRegex(ValueError, "controlled request"):
            module.verify(self.packet, diagnostic_fixture=True)

    def test_sunset_boundary_requires_matching_source_time(self):
        self.data["scene"]["timing_request"] = "sunset_plus_30min"
        self.save()
        with self.assertRaisesRegex(ValueError, "sunset offset"):
            module.verify(self.packet, diagnostic_fixture=True)

    def test_astronomical_source_mismatch_rejected(self):
        self.data["scene"]["sunrise_local"] = "2026-11-24T06:31:00-08:00"
        self.save()
        with self.assertRaisesRegex(ValueError, "astronomical source differs"):
            module.verify(self.packet, diagnostic_fixture=True)

    def test_constructed_lamps_and_map_readback(self):
        class Adapter:
            def loaded_map_bytes(self):
                return (self_root / "map_opendrive.txt").read_bytes()

            def sha_bytes(self, data):
                import hashlib
                return hashlib.sha256(data).hexdigest()

            def verify_sidewalk(self, route, sidewalk):
                return route["surface"] == "roadway" and sidewalk["surface"] == "sidewalk"

            def spawn_vehicle(self, blueprint, route):
                return blueprint

            def vehicle_blueprint_id(self, ego):
                return ego

            def set_lamps(self, ego, head, tail):
                self.lamps = (head, tail)
                return True

            def read_lamps(self, ego):
                return self.lamps

            def set_weather(self, scene):
                return True

            def read_weather(self, scene):
                return True

            def set_route(self, ego, route, speed):
                return True

        self_root = self.root
        plan = {"assignment_id": module.ASSIGNMENT, "cases": [
            {"case_id": self.data["case_id"], **{name: self.data["scene"][name]
             for name in (*module.REQUESTS, "discernibility_request_ft")}}]}
        plan_path = self.root / "case-plan.json"
        plan_path.write_text(json.dumps(plan) + "\n", encoding="utf-8")
        result = lamp_controls.prepare(Adapter(), self.packet, plan_path, diagnostic_fixture=True)
        self.assertEqual(result["requested_lamps"], {"head": True, "tail": True})
        self.assertEqual(result["physical_completion"], "unverified")
        self.data["scene"]["lit_state_request"] = "head_off"
        self.save()
        with self.assertRaisesRegex(ValueError, "controlled case request differs"):
            lamp_controls.prepare(Adapter(), self.packet, plan_path, diagnostic_fixture=True)

    def test_comparison_preserves_fixed_original_sources(self):
        other = json.loads(json.dumps(self.data))
        other["case_id"] = module.ASSIGNMENT + "__night_moving_head_off"
        other["scene"]["lit_state_request"] = "head_off"
        other_path = self.root / "other-packet.json"
        other_path.write_text(json.dumps(other) + "\n", encoding="utf-8")
        requests = (*module.REQUESTS, "discernibility_request_ft")
        plan = {"cases": [
            {"case_id": packet["case_id"], **{key: packet["scene"][key] for key in requests}}
            for packet in (self.data, other)],
            "comparisons": [{"comparison_id": "lamp_state", "case_ids":
                              [self.data["case_id"], other["case_id"]],
                              "vary_fields": ["lit_state_request"]}]}
        plan_path = self.root / "plan.json"
        plan_path.write_text(json.dumps(plan) + "\n", encoding="utf-8")
        result = pair_audit.audit(plan_path, "lamp_state", [self.packet, other_path],
                                  diagnostic_fixture=True)
        self.assertEqual(result["observed_changed_fields"], ["lit_state_request"])
        other["scene"]["route"]["waypoints"] = [[0, 0], [20, 0]]
        other_path.write_text(json.dumps(other) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "undeclared changed scene fields"):
            pair_audit.audit(plan_path, "lamp_state", [self.packet, other_path],
                             diagnostic_fixture=True)


if __name__ == "__main__":
    unittest.main()
