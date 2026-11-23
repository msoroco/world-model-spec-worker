"""Exercise saved analysis against a closed diagnostic source-bound attempt."""

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from native_camera import VIEWS
from owner_release import release
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
        self.fixture = fixture
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
                  "native_process": {"pid": 99999999, "proc_start_ticks": 1},
                  "site_packet_sha256": source_hash}
        (self.attempt / "native-run-status.json").write_text(json.dumps(status))
        (self.attempt / "native-exit.json").write_text(json.dumps({
            "event": "native_exit_pending_process_termination",
            "case_id": self.case_id,
            "native_process": status["native_process"],
            "native_run_status_sha256": sha(self.attempt / "native-run-status.json")}))
        release(self.attempt, liveness_probe=lambda _: False)
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
                          "controls": {"ego": {"throttle": 0., "brake": 1.}},
                          "ego": {"position_m": [-3., -4., 0.],
                                  "velocity_mps": [0., 0., 0.],
                                  "heading_deg": 0.,
                                  "bbox_half_extent_m": [2., .9, .7],
                                  "actor_id": 1},
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
        self.assertEqual(result["realized_observables"]["minimum_stopped_lateral_offset_from_reviewed_rightmost_m"], 0.)
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

    def test_approach_then_front_bumper_stop_can_complete_engineering_maneuver(self):
        path = self.attempt / "trace.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for index, row in enumerate(rows[:100]):
            row["ego"]["position_m"][0] = -10. + index * .07
            row["ego"]["velocity_mps"] = [1.4, 0., 0.]
            row["controls"]["ego"] = {"throttle": .3, "brake": 0.}
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        receipt_path = self.attempt / "media-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["trace_sha256"] = sha(path)
        receipt_path.write_text(json.dumps(receipt))
        _, result = analyze(self.attempt)
        self.assertTrue(result["maneuver_completed"])
        self.assertFalse(result["physical_acceptance_claimed"])
        self.assertEqual(result["legal_judgment"], "unresolved")

    def test_ego_outside_reviewed_highway_rejected_even_with_matching_receipt(self):
        path = self.attempt / "trace.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0]["ego"]["position_m"][1] = -5.5
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        receipt_path = self.attempt / "media-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["trace_sha256"] = sha(path)
        receipt_path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "footprint leaves reviewed highway"):
            analyze(self.attempt)

    def test_two_queues_depend_on_original_footprints_and_overlap(self):
        case = self.fixture.cases[1]
        self.case_id = case["case_id"]
        packet_path, _ = self.fixture.packet(case)
        shutil.rmtree(self.attempt / "site")
        retained = retain_site_sources(self.attempt, packet_path, self.fixture.plan,
                                       self.case_id)
        source_hash = sha(retained)
        status_path = self.attempt / "native-run-status.json"
        status = json.loads(status_path.read_text())
        status.update(case_id=self.case_id, site_packet_sha256=source_hash)
        status_path.write_text(json.dumps(status))
        exit_path = self.attempt / "native-exit.json"
        exited = json.loads(exit_path.read_text())
        exited.update(case_id=self.case_id,
                      native_run_status_sha256=sha(status_path))
        exit_path.write_text(json.dumps(exited))
        release_path = self.attempt / "owner-release.json"
        released = json.loads(release_path.read_text())
        released.update(case_id=self.case_id,
                        native_run_status_sha256=sha(status_path),
                        native_exit_sha256=sha(exit_path))
        release_path.write_text(json.dumps(released))
        trace_path = self.attempt / "trace.jsonl"
        rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
        for row in rows:
            row["case_id"] = self.case_id
            row["source_packet_sha256"] = source_hash
            row["companion"] = {"position_m": [-3., -1., 0.],
                                "velocity_mps": [0., 0., 0.],
                                "heading_deg": 0.,
                                "bbox_half_extent_m": [2., .9, .7],
                                "actor_id": 2}
        trace_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        receipt_path = self.attempt / "media-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt.update(trace_sha256=sha(trace_path), source_packet_sha256=source_hash)
        receipt_path.write_text(json.dumps(receipt))
        _, result = analyze(self.attempt)
        observed = result["realized_observables"]
        self.assertEqual(observed["two_queue_aligned_frame_count"], 900)
        self.assertEqual(observed["first_two_queue_alignment"]["lateral_center_separation_m"], 3.)
        for row in rows:
            row["companion"]["position_m"][0] = -9.
        trace_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        receipt["trace_sha256"] = sha(trace_path)
        receipt_path.write_text(json.dumps(receipt))
        _, result = analyze(self.attempt)
        self.assertEqual(result["realized_observables"]["two_queue_aligned_frame_count"], 0)


if __name__ == "__main__":
    unittest.main()
