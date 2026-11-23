"""Saved-only finalizer tests with explicitly synthetic Native-shaped sources."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from saved_conditions import seal
from saved_measurement import finalize_attempt, sha


CASE_ID = "testing__C179789__NRS-484B-600-1a__motor_vehicle_driver__reference"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def fixture(attempt: Path):
    attempt.mkdir(parents=True)
    source_hash, map_hash = "a" * 64, "b" * 64
    setup = {"case_id": CASE_ID, "variables": {
        "ego_speed_request_mps": 8, "leader_initial_gap_m": 30,
        "surface_wetness_request": .1, "highway_width_m": 7.2,
        "native_precipitation_request": 0, "native_fog_request": 0},
        "source_packet_sha256": source_hash, "opendrive_sha256": map_hash,
        "paved_road": True, "travel_direction": "forward"}
    path = attempt / "authored-setup.json"
    path.write_text(json.dumps(setup))
    (attempt / "authored-setup-seal.json").write_text(json.dumps({
        "format": "c179789-authored-setup-v1", "case_id": CASE_ID,
        "sha256": sha(path)}))
    ids = {"ego_actor_id": 1, "leader_actor_id": 2, "road_id": 3,
           "lane_id": -1, "opendrive_sha256": map_hash}
    conditions, trace, mapping = [], [], []
    for index in range(900):
        frame = 400 + index
        time_s = 20 + index * .05
        conditions.append({"frame": frame, "time_s": time_s, "source_frame": frame,
                           "ego_speed_mps": 8., "leader_gap_m": 30.,
                           "surface_wetness": .1, "highway_width_m": 7.2,
                           "precipitation_strength": 0., "fog_density": 0.,
                           "tire_friction": 2., "source_ids": ids})
        camera = {name: {"sha256": "c" * 64} for name in VIEWS}
        trace.append({"frame": frame, "time_s": time_s, "source_frame": frame,
                      "condition_sample_index": index, "camera_sources": camera,
                      "source_packet_sha256": source_hash,
                      "position_m": [index * .4, 0, 0], "control": {"throttle": .2},
                      "physical_acceptance_claimed": False})
        mapping.append({"video_frame": index, "carla_frame": frame,
                        "native_frame": frame, "time_s": time_s,
                        "camera_source_sha256": {name: "c" * 64 for name in VIEWS}})
    seal(attempt, CASE_ID, conditions, diagnostic_fixture=True)
    for name, rows in (("trace.jsonl", trace), ("video_frames.jsonl", mapping)):
        (attempt / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
    videos = {}
    for name in VIEWS:
        video = attempt / (name + ".mkv")
        video.write_bytes((name + " synthetic diagnostic bytes").encode())
        videos[name] = sha(video)
    receipt = {"format": "c179789-original-four-camera-media-v1",
               "frames": 900, "source_packet_sha256": source_hash,
               "trace_sha256": sha(attempt / "trace.jsonl"),
               "frame_map_sha256": sha(attempt / "video_frames.jsonl"),
               "video_sha256": videos, "physical_acceptance_claimed": False}
    (attempt / "media-receipt.json").write_text(json.dumps(receipt))
    (attempt / "native-run-status.json").write_text(json.dumps({
        "case_id": CASE_ID, "capture": {"frames": 900},
        "restoration": {"restored": True}, "errors": [],
        "physical_acceptance_claimed": False}))


class SavedMeasurementTests(unittest.TestCase):
    def setUp(self):
        root = HERE.parents[1] / ".runtime-work"
        root.mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(temp.cleanup)
        self.attempt = Path(temp.name) / "attempt"
        fixture(self.attempt)

    def test_saved_result_keeps_source_and_judgment_distinct(self):
        report = finalize_attempt(self.attempt, self.attempt / "analysis-report.json")
        result = json.loads((self.attempt / "result.json").read_text())
        self.assertEqual(report["case_id"], CASE_ID)
        self.assertEqual(len(result["target_checks"]), 6)
        self.assertIn("basic_speed_observation", report["measurements"])
        self.assertEqual(result["measured_values"]["conditions"]["provenance_kind"],
                         "synthetic_fixture")
        self.assertEqual(result["measured_values"]["legal_judgment"], "unresolved")
        self.assertFalse(result["physical_acceptance_claimed"])
        self.assertFalse(result["setup_confirmed"])
        self.assertEqual(len(list((self.attempt / "channels").glob("*"))), 9)
        with self.assertRaisesRegex(ValueError, "retain previous saved analysis"):
            finalize_attempt(self.attempt, self.attempt / "analysis-report.json")

    def test_changed_condition_or_video_bytes_rejected(self):
        raw = self.attempt / "original-conditions.jsonl"
        raw.write_bytes(raw.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "source hash differs"):
            finalize_attempt(self.attempt, self.attempt / "analysis-report.json")
        self.assertFalse((self.attempt / "result.json").exists())

    def test_missing_video_and_frame_join_rejected(self):
        (self.attempt / "overview.mkv").unlink()
        with self.assertRaisesRegex(ValueError, "video bytes differ"):
            finalize_attempt(self.attempt, self.attempt / "analysis-report.json")
        (self.attempt / "overview.mkv").write_bytes(b"overview synthetic diagnostic bytes")
        trace = self.attempt / "trace.jsonl"
        rows = [json.loads(line) for line in trace.read_text().splitlines()]
        rows[1]["condition_sample_index"] = 5
        trace.write_text("".join(json.dumps(row) + "\n" for row in rows))
        with self.assertRaisesRegex(ValueError, "trace, condition and frame map join differs"):
            finalize_attempt(self.attempt, self.attempt / "analysis-report.json")

    def test_measurement_contract_missing_source_rejected(self):
        contract = json.loads((HERE / "measurement-contract.json").read_text())
        self.assertEqual(contract["requirements"][0]["output_key"],
                         "basic_speed_observation")
        (self.attempt / "original-conditions.jsonl").unlink()
        with self.assertRaisesRegex(ValueError, contract["negative"]["error_contains"]):
            finalize_attempt(self.attempt, self.attempt / "analysis-report.json")

    def test_resealed_unassigned_case_rejected(self):
        path = self.attempt / "authored-setup.json"
        setup = json.loads(path.read_text())
        setup["case_id"] = "unassigned-case"
        path.write_text(json.dumps(setup))
        seal_path = self.attempt / "authored-setup-seal.json"
        seal_doc = json.loads(seal_path.read_text())
        seal_doc.update(case_id="unassigned-case", sha256=sha(path))
        seal_path.write_text(json.dumps(seal_doc))
        with self.assertRaisesRegex(ValueError, "one exact paved-road case"):
            finalize_attempt(self.attempt, self.attempt / "analysis-report.json")


if __name__ == "__main__":
    unittest.main()
