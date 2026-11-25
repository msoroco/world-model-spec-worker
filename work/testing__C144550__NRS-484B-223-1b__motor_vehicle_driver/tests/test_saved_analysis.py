import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path.cwd() / "runtime" / "scenario_pipeline"))

from analysis import build_report, write_selected_result
from native_construction import ASSIGNMENT
from worker_exchange.measurement_contract import verify_report


def put(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SavedAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = ASSIGNMENT + "__both_observed"
        config = json.loads((ROOT / "config.json").read_text())
        config["selected_case_id"] = self.case
        put(self.root / "config.json", config)
        put(self.root / "acquisition-provenance.json", {
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True})
        anchors = [{"frame": i + 100, "t_s": i * .05} for i in range(900)]
        packets = {
            "frame_map": {"samples": anchors},
            "ego_pose": {"source_lane_id": "source-lane", "lane_geometry_source": "reviewed-map",
                "samples": [{**row, "x_m": i * .05, "y_m": 3.5 if i == 899 else 0.,
                             "source_lane_offset_m": .06 if i >= 4 else 0.}
                            for i, row in enumerate(anchors)]},
            "native_signal": {"readback_source": "CARLA original API",
                "samples": [{**row, "left_signal": i >= 1, "right_signal": False}
                            for i, row in enumerate(anchors)]},
            "driver_check": {"readback_source": "separate original driver input",
                "observation_method": "original event", "samples": [
                    {**row, "driver_check_observed": i == 2} for i, row in enumerate(anchors)]}}
        inventory = {"case_id": self.case, "source_kind": "original_native",
                     "original_trace_id": "synthetic-test-source", "sources": {}}
        for name, packet in packets.items():
            packet.update({"case_id": self.case, "source_kind": "original_native"})
            digest = put(self.root / (name + ".json"), packet)
            inventory["sources"][name] = {"path": name + ".json", "sha256": digest}
        put(self.root / "readback-inventory.json", inventory)
        traffic = [{**row, "target_x_m": 20., "target_y_m": 3.5} for row in anchors]
        driver = [{**row, "source_kind": "original_driver_input",
                   "source_id": "separate-driver-source", "observed": i == 2}
                  for i, row in enumerate(anchors)]
        def lines(name, rows):
            path = self.root / name
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            return hashlib.sha256(path.read_bytes()).hexdigest()
        traffic_sha = lines("target-traffic-history.jsonl", traffic)
        driver_sha = lines("original-driver-input.jsonl", driver)
        camera_root = self.root / "original-camera-frames"
        camera_root.mkdir()
        camera = [{"frame": i, "native_frame": row["frame"],
                   "native_elapsed_s": row["t_s"], "views": {}}
                  for i, row in enumerate(anchors)]
        camera_sha = put(camera_root / "camera-manifest.json", camera)
        put(self.root / "lane-change-capture-receipt.json", {
            "native_frame_count": 900, "readback_inventory": inventory,
            "target_traffic": {"sha256": traffic_sha},
            "original_driver_input": {"sha256": driver_sha,
                                      "source_id": "separate-driver-source"},
            "camera_manifest": {"sha256": camera_sha}})
        put(self.root / "reviewed-site.json", {
            "reviewed_provenance": {"reviewer": "synthetic test only"},
            "lanes": {"source": {"lane_id": "source-lane"},
                      "destination": {"lane_id": "destination-lane",
                          "centerline_world_xyz_m": [[i * 5., 3.5, 0.] for i in range(10)]}},
            "ego_blueprint": "vehicle.test", "target_vehicle_blueprint": "vehicle.target",
            "target_spawn_xyz_yaw": [20., 3.5, 0., 0.],
            "camera_poses_xyz_pitch_yaw": {"overview": [0, 0, 10, 0, 0]}})
        lines("trace.jsonl", [{"frame": row["frame"], "time_s": row["t_s"]}
                              for row in anchors])
        lines("video_frames.jsonl", [{"carla_frame": row["frame"], "time_s": row["t_s"]}
                                     for row in anchors])
        for name in ("overview", "approach", "reference_corner", "driver_reference", "raw"):
            (self.root / (name + ".mkv")).write_bytes(b"synthetic-test-placeholder")

    def report(self):
        with patch("analysis.audit_camera_sources", return_value={
            "joined_frames": 900, "physical_pixel_review": "unresolved"}):
            return build_report(self.root)

    def test_saved_source_joins_and_result_preserve_legal_uncertainty(self):
        report = self.report()
        self.assertTrue(report["measurements"]["signal_precedes_center_departure"])
        self.assertTrue(report["measurements"]["driver_check_observed_before_departure"])
        self.assertFalse(report["legal_verdict_claimed"])
        contract = json.loads((ROOT / "measurement-contract.json").read_text())
        measured = verify_report(contract, report, self.root)
        self.assertEqual(len(measured), 3)
        result = write_selected_result(self.root, report)
        self.assertEqual(result["case_id"], self.case)
        self.assertFalse(result["legal_acceptance_claimed"])
        self.assertEqual(result["physical_checks"]["maneuver"]["status"], "met")

    def test_missing_or_changed_independent_source_fails(self):
        source = self.root / "original-driver-input.jsonl"
        original = source.read_text()
        source.unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source"):
            self.report()
        source.write_text(original.replace("\n", " \n", 1))
        with self.assertRaisesRegex(ValueError, "original independent driver-input SHA256"):
            self.report()


if __name__ == "__main__":
    unittest.main()
