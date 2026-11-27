import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_audit import audit, audit_saved_pair
from comparison_source_guard import audit_guarded_pair, audit_saved_attempts, check_record


AID = "testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator"


def record(suffix, speed=3.0, visibility="clear", surface="dry", pedestrians="none"):
    return {"case_id": AID + "__" + suffix, "source_kind": "original_native",
            "legal_prudence": "unresolved", "samples": [{"time_s": 0.0, "speed_mps": speed}],
            "summary": {"mean_speed_mps": speed}, "condition_samples": [{"time_s": 0.0,
                "weather": "clear", "surface": surface, "visibility": visibility,
                "pedestrians": pedestrians, "curvature": "straight"}], "context": {
                "jurisdiction": "Las Vegas", "bicycle_classification": "human-powered",
                "alley_route": "same route", "rack_geometry": "same rack"}}


class ComparisonAuditTest(unittest.TestCase):
    def setUp(self):
        self.plan = {"comparisons": [
            {"comparison_id": "speed_under_clear_conditions", "case_ids": [AID + "__reference", AID + "__faster"]},
            {"comparison_id": "visibility_at_reference_speed", "case_ids": [AID + "__reference", AID + "__reduced_visibility"]},
            {"comparison_id": "pedestrian_at_reference_speed", "case_ids": [AID + "__reference", AID + "__pedestrian_near_rack"]},
            {"comparison_id": "surface_at_reference_speed", "case_ids": [AID + "__reference", AID + "__wet_surface"]},
        ], "cases": [{"case_id": AID + "__" + suffix,
                      "controller": {"target_speed_mps": speed}}
                     for suffix, speed in (("reference", 3.0), ("faster", 5.0),
                                           ("reduced_visibility", 3.0),
                                           ("pedestrian_near_rack", 3.0),
                                           ("wet_surface", 3.0))]}

    def test_speed_change(self):
        self.assertTrue(audit(self.plan, "speed_under_clear_conditions", record("reference"), record("faster", 5.0))["passed"])

    def test_visibility_change(self):
        self.assertTrue(audit(self.plan, "visibility_at_reference_speed", record("reference"), record("reduced_visibility", visibility="reduced"))["passed"])

    def test_pedestrian_and_surface_change(self):
        self.assertTrue(audit(self.plan, "pedestrian_at_reference_speed", record("reference"),
                              record("pedestrian_near_rack", pedestrians="near_rack"))["passed"])
        self.assertTrue(audit(self.plan, "surface_at_reference_speed", record("reference"),
                              record("wet_surface", surface="wet"))["passed"])

    def test_independent_delivery_receipt_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            paths = []
            receipts = []
            for suffix, speed in (("reference", 3.0), ("faster", 5.0)):
                path = base / (suffix + ".json")
                path.write_text(json.dumps(record(suffix, speed)))
                receipt_path = base / (suffix + "-delivery.json")
                receipt_path.write_text(json.dumps({
                    "format": "worker-delivery-audit", "passed": True,
                    "case_id": AID + "__" + suffix,
                    "native_result_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "checks": ["native_source", "all_participants", "time_join",
                               "full_video_decode", "actual_pixels", "physical_completion"]}))
                paths.append(path)
                receipts.append(receipt_path)
            result = audit_guarded_pair(self.plan, "speed_under_clear_conditions", *paths, *receipts)
            self.assertTrue(result["independent_delivery_audits"])
            tampered = json.loads(receipts[1].read_text())
            tampered["native_result_sha256"] = "0" * 64
            receipts[1].write_text(json.dumps(tampered))
            with self.assertRaisesRegex(ValueError, "source-bound"):
                audit_guarded_pair(self.plan, "speed_under_clear_conditions", *paths, *receipts)

    def test_missing_measured_difference_rejected(self):
        with self.assertRaisesRegex(ValueError, "measured speed"):
            audit(self.plan, "speed_under_clear_conditions", record("reference"), record("faster"))

    def test_fixed_condition_change_rejected(self):
        right = record("faster", 5.0)
        right["condition_samples"][0]["surface"] = "wet"
        with self.assertRaisesRegex(ValueError, "fixed condition changed"):
            audit(self.plan, "speed_under_clear_conditions", record("reference"), right)

    def test_case_identity_rejected(self):
        with self.assertRaisesRegex(ValueError, "case identity"):
            audit(self.plan, "speed_under_clear_conditions", record("reference"), record("reduced_visibility", 5.0))

    def test_nonoriginal_rejected(self):
        right = record("faster", 5.0)
        right["source_kind"] = "synthetic_fixture"
        with self.assertRaisesRegex(ValueError, "original measurement"):
            audit(self.plan, "speed_under_clear_conditions", record("reference"), right)

    def test_reported_mean_must_match_original_speeds(self):
        right = record("faster", 5.0)
        right["summary"]["mean_speed_mps"] = 6.0
        with self.assertRaisesRegex(ValueError, "reported mean"):
            check_record(right)

    def test_source_approach_mean_excludes_post_route_stop(self):
        candidate = record("reference")
        candidate["samples"] = [
            {"time_s": i * .05, "x_m": -25.0 + i * .1,
             "speed_mps": 3.0 if i < 500 else 0.0}
            for i in range(900)]
        candidate["condition_samples"] = [{"time_s": i * .05} for i in range(900)]
        candidate["summary"] = {
            "mean_speed_mps": 3.0,
            "episode_mean_speed_mps": 3.0 * 500 / 900,
            "approach_window": {"start_x_m": -20.0, "end_x_m": 0.0,
                                "sample_count": 201, "source_verified": True}}
        check_record(candidate)
        candidate["summary"]["mean_speed_mps"] = 3.0 * 500 / 900
        with self.assertRaisesRegex(ValueError, "reported mean"):
            check_record(candidate)

    def test_condition_time_must_join_original_speed_time(self):
        right = record("faster", 5.0)
        right["condition_samples"][0]["time_s"] = 0.05
        with self.assertRaisesRegex(ValueError, "condition source time"):
            check_record(right)

    def test_invalid_original_speed_rejected(self):
        right = record("faster", 5.0)
        right["samples"][0]["speed_mps"] = float("nan")
        with self.assertRaisesRegex(ValueError, "invalid original speed"):
            check_record(right)

    def test_saved_attempts_recompute_original_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            attempts = []
            receipts = []
            own = Path(__file__).resolve().parents[1]
            manifest = json.loads((own / "execution-manifest.json").read_text())
            for suffix, speed in (("reference", 3.0), ("faster", 5.0)):
                attempt = base / suffix
                attempt.mkdir()
                case = AID + "__" + suffix
                selected = next(item for item in manifest["cases"] if item["case_id"] == case)
                construction = json.loads((own / selected["construction"]).read_text())
                (attempt / "construction.json").write_text(json.dumps(construction))
                config = next(json.loads(item["content"]) for item in construction["files"]
                              if item["path"] == "config.json")
                (attempt / "config.json").write_text(json.dumps(config))
                frames = [{"frame": 1000 + n, "time_s": (n + 1) / 20}
                          for n in range(900)]
                motion = {"case_id": case, "samples": [dict(row, velocity_mps=[speed, 0, 0])
                                                       for row in frames]}
                context = {"case_id": case, "jurisdiction": {"city_of_las_vegas": True,
                           "source": "test source"}, "bicycle_classification": {"human_powered": True,
                           "moped": False, "source": "test source"},
                           "alley_route": {"source": "test source"},
                           "rack_geometry": {"source": "test source"},
                           "samples": [dict(row, weather="clear", surface="dry", visibility="clear",
                                            pedestrians="none", curvature="straight") for row in frames]}
                sources = {}
                for key, name, value in (("frame_map", "frame-map.json", {"frames": frames}),
                                         ("bicycle_motion", "bicycle-motion.json", motion),
                                         ("context", "context.json", context)):
                    path = attempt / name
                    path.write_text(json.dumps(value))
                    sources[key] = {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                (attempt / "inventory.json").write_text(json.dumps({"case_id": case,
                    "source_kind": "original_native", "sources": sources}))
                native = attempt / "result.json"
                native.write_text(json.dumps({"case_id": case, "diagnostic_fixture": False,
                    "target_checks": [{"target": "bicycle_speed_mps", "requested": speed,
                                       "matched": True}]}))
                receipt = attempt / "delivery-audit.json"
                receipt.write_text(json.dumps({"format": "worker-delivery-audit", "passed": True,
                    "case_id": case, "native_result_sha256": hashlib.sha256(native.read_bytes()).hexdigest(),
                    "checks": ["native_source", "all_participants", "time_join",
                               "full_video_decode", "actual_pixels", "physical_completion"]}))
                attempts.append(attempt)
                receipts.append(receipt)
            result = audit_saved_attempts(self.plan, "speed_under_clear_conditions",
                                          *attempts, *receipts)
            self.assertTrue(result["independent_delivery_audits"])
            self.assertEqual(len(result["original_inventory_sha256"]), 2)
            self.assertEqual(len(result["selected_camera_contract"]["source_sha256"]), 64)
            fallback = next(item for item in selected["candidates"] if item["id"] == "fallback1")
            fallback_construction = json.loads((own / fallback["construction"]).read_text())
            (attempts[1] / "construction.json").write_text(json.dumps(fallback_construction))
            (attempts[1] / "candidate-selection.json").write_text(json.dumps({
                "case_id": AID + "__faster", "candidate_id": "fallback1",
                "construction_sha256": fallback["construction_sha256"],
                "manifest_sha256": hashlib.sha256((own / "execution-manifest.json").read_bytes()).hexdigest()}))
            with self.assertRaisesRegex(ValueError, "fixed camera source"):
                audit_saved_attempts(self.plan, "speed_under_clear_conditions",
                                     *attempts, *receipts)
            (attempts[1] / "candidate-selection.json").unlink()
            (attempts[1] / "construction.json").write_text(json.dumps(construction))
            changed_native = json.loads((attempts[1] / "result.json").read_text())
            changed_native["target_checks"][0]["requested"] = 3.0
            (attempts[1] / "result.json").write_text(json.dumps(changed_native))
            with self.assertRaisesRegex(ValueError, "speed target differs"):
                audit_saved_attempts(self.plan, "speed_under_clear_conditions",
                                     *attempts, *receipts)
            changed_native["target_checks"][0]["requested"] = speed
            (attempts[1] / "result.json").write_text(json.dumps(changed_native))
            inventory_path = attempts[0] / "inventory.json"
            inventory = json.loads(inventory_path.read_text())
            inventory["diagnostic_fixture"] = True
            inventory_path.write_text(json.dumps(inventory))
            with self.assertRaisesRegex(ValueError, "non-diagnostic original inventory"):
                audit_saved_attempts(self.plan, "speed_under_clear_conditions",
                                     *attempts, *receipts)
            inventory.pop("diagnostic_fixture")
            inventory_path.write_text(json.dumps(inventory))
            motion_path = attempts[1] / "bicycle-motion.json"
            changed = json.loads(motion_path.read_text())
            changed["samples"][2]["velocity_mps"][0] = 12
            motion_path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "stale required source"):
                audit_saved_attempts(self.plan, "speed_under_clear_conditions",
                                     *attempts, *receipts)
            changed["samples"][2]["velocity_mps"][0] = 5.0
            changed["samples"].append({"frame": 1900, "time_s": 901 / 20,
                                       "velocity_mps": [5.0, 0, 0]})
            motion_path.write_text(json.dumps(changed))
            context_path = attempts[1] / "context.json"
            context = json.loads(context_path.read_text())
            context["samples"].append({"frame": 1900, "time_s": 901 / 20,
                                       "weather": "clear", "surface": "dry",
                                       "visibility": "clear", "pedestrians": "none",
                                       "curvature": "straight"})
            context_path.write_text(json.dumps(context))
            map_path = attempts[1] / "frame-map.json"
            frame_map = json.loads(map_path.read_text())
            frame_map["frames"].append({"frame": 1900, "time_s": 901 / 20})
            map_path.write_text(json.dumps(frame_map))
            updated_inventory_path = attempts[1] / "inventory.json"
            updated_inventory = json.loads(updated_inventory_path.read_text())
            for key, path in (("frame_map", map_path),
                              ("bicycle_motion", motion_path), ("context", context_path)):
                updated_inventory["sources"][key]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            updated_inventory_path.write_text(json.dumps(updated_inventory))
            with self.assertRaisesRegex(ValueError, "exact 900-frame"):
                audit_saved_attempts(self.plan, "speed_under_clear_conditions",
                                     *attempts, *receipts)


if __name__ == "__main__":
    unittest.main()
