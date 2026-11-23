"""Exercise saved analysis against a closed diagnostic source-bound attempt."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from native_camera import VIEWS
from runner import retain_site_sources
from saved_measurement import analyze, finalize_attempt, sha
import test_native_scene as scene_fixture


class SavedMeasurementTests(unittest.TestCase):
    def setUp(self):
        private = ROOT / ".runtime-work"
        private.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=private)
        self.addCleanup(self.temp.cleanup)
        self.attempt = Path(self.temp.name) / "attempt"
        self.attempt.mkdir()
        fixture = scene_fixture.NativeSceneTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        case = fixture.cases[0]
        self.case_id = case["case_id"]
        packet_path, _ = fixture.packet(case)
        retained = retain_site_sources(self.attempt, packet_path, fixture.plan,
                                       self.case_id)
        source_hash = sha(retained)
        status = {"case_id": self.case_id, "errors": [],
                  "capture": {"frames": 900},
                  "restoration": {"restored": True},
                  "retained_site_packet": "site/packet.json",
                  "site_packet_sha256": source_hash}
        (self.attempt / "native-run-status.json").write_text(json.dumps(status))
        videos = {}
        for name, _, _ in VIEWS:
            video = self.attempt / (name + ".mkv")
            video.write_bytes((name + " diagnostic video bytes").encode())
            videos[name] = sha(video)
        trace, mapping = [], []
        for index in range(900):
            frame, time_s = 1000 + index, index * .05
            hashes = {name: hashlib.sha256(f"{name}:{frame}".encode()).hexdigest()
                      for name, _, _ in VIEWS}
            camera = {name: {"sha256": hashes[name]} for name in hashes}
            trace.append({"case_id": self.case_id, "frame": frame,
                          "source_frame": frame, "time_s": time_s,
                          "source_packet_sha256": source_hash,
                          "physical_acceptance_claimed": False,
                          "camera_sources": camera,
                          "ego": {"position_m": [-1., -4., 0.],
                                  "velocity_mps": [0., 0., 0.]},
                          "companion": None})
            mapping.append({"video_frame": index, "carla_frame": frame,
                            "native_frame": frame, "time_s": time_s,
                            "camera_source_sha256": hashes})
        (self.attempt / "trace.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in trace))
        (self.attempt / "video_frames.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in mapping))
        receipt = {"format": "c202480-original-four-camera-media-v1",
                   "frames": 900, "source_packet_sha256": source_hash,
                   "trace_sha256": sha(self.attempt / "trace.jsonl"),
                   "frame_map_sha256": sha(self.attempt / "video_frames.jsonl"),
                   "video_sha256": videos}
        (self.attempt / "media-receipt.json").write_text(json.dumps(receipt))

    def test_closed_source_bound_stop_measurement(self):
        report = finalize_attempt(self.attempt, self.attempt / "analysis-report.json")
        result = json.loads((self.attempt / "result.json").read_text())
        self.assertEqual(report["legal_judgment"], "unresolved")
        self.assertEqual(result["physical_checks"]["one_second_pre_rail_stationary_observation"]["status"], "met")
        self.assertFalse(result["maneuver_completed"])
        self.assertFalse(result["physical_acceptance_claimed"])
        with self.assertRaisesRegex(ValueError, "retain previous saved analysis"):
            finalize_attempt(self.attempt, self.attempt / "analysis-report.json")

    def test_motion_failure_is_not_reported_as_stop(self):
        path = self.attempt / "trace.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for row in rows:
            row["ego"]["velocity_mps"] = [1., 0., 0.]
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        receipt_path = self.attempt / "media-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["trace_sha256"] = sha(path)
        receipt_path.write_text(json.dumps(receipt))
        _, result = analyze(self.attempt)
        self.assertEqual(result["physical_checks"]["one_second_pre_rail_stationary_observation"]["status"], "not_met")

    def test_changed_original_trace_rejected(self):
        path = self.attempt / "trace.jsonl"
        path.write_text(path.read_text().replace('"frame": 1000', '"frame": 9999', 1))
        with self.assertRaisesRegex(ValueError, "media/source receipt differs"):
            analyze(self.attempt)


if __name__ == "__main__":
    unittest.main()
