"""Source-shaped engineering planning tests; no physical or legal acceptance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from driveway_construction import build_plan
from native_driveway import retain_packet, validate_packet, validate_spawn
from parking_controller import ParkingController


class DrivewayConstructionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT.parents[1] / ".runtime-work")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.plan = json.loads((ROOT / "case-plan.json").read_text())

    def packet(self, kind):
        names = ("opendrive", "mouth", "frontage", "driveway_use", "responsible_person",
                 "relationship", "purpose", "traffic_direction", "postal_status")
        sources = {}
        for name in names:
            path = self.base / (kind + "-" + name + ".txt")
            path.write_text("Reviewed source-shaped diagnostic: " + kind + " " + name + "\n")
            sources[name] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                             "reviewer": "diagnostic tester", "citation": "fixture:" + name}
        packet = {"review_status": "reviewed", "reviewer": "diagnostic tester",
                  "driveway_kind": kind, "driveway_id": kind + "-1",
                  "vehicle_blueprint_id": "vehicle.diagnostic", "vehicle_length_m": 4.5,
                  "vehicle_width_m": 1.8, "road_start_xy_m": [0, 0], "road_end_xy_m": [100, 0],
                  "mouth_start_xy_m": [50, -2], "mouth_end_xy_m": [50, 2],
                  "sources": sources}
        path = self.base / (kind + "-survey.json")
        path.write_text(json.dumps(packet) + "\n")
        return path, packet

    def test_all_sixteen_exact_requests_and_spatial_brackets(self):
        packets = {kind: self.packet(kind)[0] for kind in ("public", "private")}
        for case in self.plan["cases"]:
            with self.subTest(case=case["case_id"]):
                request = build_plan(packets[case["driveway_kind"]], case["case_id"])
                self.assertEqual(request["activity_request"], case["activity"])
                self.assertEqual(request["relationship_context_request"], case["driver_relationship"])
                self.assertEqual(request["capture"]["cameras"],
                                 ["overview", "approach", "reference_corner", "driver_reference"])
                self.assertFalse(request["physical_acceptance_claimed"])
                distance = request["planned_full_footprint_to_mouth_m"]
                if case["position_target"] == "front":
                    self.assertLessEqual(distance, 0.05)
                elif case["position_target"] == "within_5ft":
                    self.assertTrue(0 < distance < 1.524)
                else:
                    self.assertGreater(distance, 1.524)

    def test_changed_source_and_kind_mismatch_rejected(self):
        packet, data = self.packet("public")
        case = self.plan["cases"][0]["case_id"]
        (self.base / data["sources"]["mouth"]["path"]).write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "source bytes changed"):
            build_plan(packet, case)
        other, _ = self.packet("private")
        with self.assertRaisesRegex(ValueError, "driveway kind differs"):
            build_plan(other, case)

    def test_unachievable_geometry_rejected(self):
        packet, data = self.packet("public")
        data["mouth_start_xy_m"] = [50, 10]
        data["mouth_end_xy_m"] = [50, 13]
        packet.write_text(json.dumps(data) + "\n")
        with self.assertRaisesRegex(ValueError, "does not put vehicle in front"):
            build_plan(packet, self.plan["cases"][0]["case_id"])

    def test_native_packet_requires_exact_context_and_camera_custody(self):
        packet, data = self.packet("public")
        case = self.plan["cases"][0]
        data["case_id"] = case["case_id"]
        data["observed_conditions"] = {name: case[name] for name in
                                       ("driveway_kind", "activity", "position_target",
                                        "driver_relationship", "necessity_or_postal_context")}
        data["spawn_xyz_m"] = [28, 0, 1]
        data["spawn_rpy_deg"] = [0, 0, 0]
        data["cameras"] = [
            {"name": name, "width": width, "height": height, "fov_deg": 75,
             "location_xyz_m": [30, 4, 5], "rotation_rpy_deg": [0, -10, 0],
             "pose_source": "diagnostic survey"}
            for name, width, height in (("overview", 1920, 1080), ("approach", 1280, 720),
                                        ("reference_corner", 1280, 720),
                                        ("driver_reference", 1280, 720))]
        packet.write_text(json.dumps(data) + "\n")
        self.assertEqual(validate_packet(packet, case["case_id"])[0]["case_id"], case["case_id"])
        data["observed_conditions"]["driver_relationship"] = "owner"
        packet.write_text(json.dumps(data) + "\n")
        with self.assertRaisesRegex(ValueError, "reviewed original condition differs"):
            validate_packet(packet, case["case_id"])
        data["observed_conditions"]["driver_relationship"] = "ordinary"
        data["cameras"][0]["width"] = 1280
        packet.write_text(json.dumps(data) + "\n")
        with self.assertRaisesRegex(ValueError, "reviewed camera profile differs"):
            validate_packet(packet, case["case_id"])

    def test_controller_preserves_requested_activity_hold(self):
        packet, _ = self.packet("public")
        case = self.plan["cases"][0]
        plan = build_plan(packet, case["case_id"])
        control = ParkingController(plan)
        self.assertEqual(control.plan["controller"]["activity"], "park")
        self.assertEqual(control.step(xy_m=plan["start_xy_m"], yaw_rad=0,
                                      speed_mps=0, time_s=0)["phase"], "approach")

    def test_reviewed_spawn_follows_each_candidate_route(self):
        packet, survey = self.packet("public")
        case = self.plan["cases"][0]["case_id"]
        forward = build_plan(packet, case, approach_direction=1)
        reverse = build_plan(packet, case, approach_direction=-1)
        survey["spawn_xyz_m"] = [*forward["start_xy_m"], 1]
        survey["spawn_rpy_deg"] = [0, 0, 0]
        self.assertTrue(validate_spawn(survey, forward))
        with self.assertRaisesRegex(ValueError, "selected candidate approach"):
            validate_spawn(survey, reverse)
        survey["spawn_xyz_m"] = [*reverse["start_xy_m"], 1]
        with self.assertRaisesRegex(ValueError, "heading differs"):
            validate_spawn(survey, reverse)
        survey["spawn_rpy_deg"] = [0, 0, 180]
        self.assertTrue(validate_spawn(survey, reverse))

    def test_reviewed_packet_bytes_retained_and_tamper_rejected(self):
        packet, survey = self.packet("public")
        hashes = {name: ref["sha256"] for name, ref in survey["sources"].items()}
        output = self.base / "original-attempt"
        output.mkdir()
        retained = retain_packet(packet, survey, hashes, output)
        self.assertEqual((output / "original-reviewed-survey.json").read_bytes(), packet.read_bytes())
        for name, ref in retained.items():
            self.assertEqual(ref["source_kind"], "original_reviewed_packet")
            self.assertEqual(hashlib.sha256((output / ref["path"]).read_bytes()).hexdigest(), hashes[name])
        (output / retained["mouth"]["path"]).write_text("tampered\n")
        with self.assertRaisesRegex(ValueError, "path collision"):
            retain_packet(packet, survey, hashes, output)


if __name__ == "__main__":
    unittest.main()
