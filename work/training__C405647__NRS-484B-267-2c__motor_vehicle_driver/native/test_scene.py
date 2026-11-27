"""Verify the controlled physical request before any CARLA acquisition."""

import copy
from enum import IntFlag
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scene import CASES, check_pair, request
from measure_readiness import CAMERA_DIMENSIONS
from from_original import convert, process
from runner import emergency_light_state, emergency_motion_control


class SceneTest(unittest.TestCase):
    def test_exact_requested_lamp_channels(self):
        class Lamps(IntFlag):
            NONE = 0
            Special1 = 1
            Special2 = 2

        self.assertEqual(emergency_light_state(Lamps, True), Lamps.Special1 | Lamps.Special2)
        self.assertEqual(emergency_light_state(Lamps, False), Lamps.NONE)

    def test_emergency_motion_target_feedback(self):
        self.assertEqual(emergency_motion_control(0.0, .5, False), (0.0, 1.0))
        throttle, brake = emergency_motion_control(0.0, .5, True)
        self.assertGreater(throttle, 0)
        self.assertEqual(brake, 0)
        throttle, brake = emergency_motion_control(1.0, .5, True)
        self.assertEqual(throttle, 0)
        self.assertGreater(brake, 0)

    def test_exact_pair_and_profile(self):
        first, second = (request(case) for case in CASES)
        self.assertTrue(check_pair(first, second)["passed"])
        self.assertEqual([camera["name"] for camera in first["cameras"]],
                         ["overview", "approach", "reference_corner", "driver_reference"])
        self.assertEqual(first["frames"], 600)
        self.assertLessEqual(first["ego_start_xyz_m"][0] +
                             first["ego_cruise_speed_mps"] * first["duration_s"],
                             first["ego_destination_xy_m"][0])
        self.assertLess(first["emergency_motion_start_frame"],
                        first["ego_response_policy"]["brake_onset_frame"])
        self.assertEqual({camera["name"]: (camera["width"], camera["height"])
                          for camera in first["cameras"]}, CAMERA_DIMENSIONS)

    def test_changed_map_or_emergency_motion_rejected(self):
        first, second = (request(case) for case in CASES)
        for change in ({"source_map": first["source_map"].replace("shoulder", "driving")},
                       {"emergency_motion_start_frame": 200},
                       {"light_request": "none"}):
            altered = copy.deepcopy(second)
            altered.update(change)
            with self.assertRaisesRegex(ValueError, "requests changed"):
                check_pair(first, altered)

    def test_original_trace_conversion_and_source_rejections(self):
        frames, actors, review = [], [], []
        for index in range(600):
            native = 30 + index
            frames.append({"video_frame": index, "native_frame": native,
                           "time_s": index / 20})
            ego_x = -80 + index * .1
            actors.append({"frame": index, "native_frame": native,
                           "time_s": index / 20,
                           "source_kind": "original_native_motion",
                           "ego_brake_request": .8 if index >= 180 else 0,
                           "ego_brake_observed": .8 if index >= 180 else 0,
                           "lamp_request": index % 10 < 5,
                           "lamp_state_observed": index % 10 < 5,
                           "actors": {
                               "ego": {"native_speed_mps": 2,
                                       "native_center_xy_m": [ego_x + .5, 1.5],
                                       "native_body_xy_m": [[ego_x, 1], [ego_x + 1, 1],
                                                            [ego_x, 2], [ego_x + 1, 2]]},
                               "emergency": {"native_speed_mps": .5,
                                             "native_center_xy_m": [15.5, 5.5],
                                             "native_body_xy_m": [[15, 5], [16, 5],
                                                                  [15, 6], [16, 6]]}}})
            review.append({"video_frame": index, "source_native_frame": native,
                           "source_camera": "approach",
                           "emergency_flashing_visible": index >= 150,
                           "emergency_motion_visible": index >= 150,
                           "hand_signal_visible": False})
        trace = convert(frames, actors, review)
        self.assertEqual(len(trace), 600)
        self.assertGreater(trace[0]["surface_gap_m"], trace[-1]["surface_gap_m"])
        self.assertEqual(trace[180]["ego_brake"], .8)
        stale = copy.deepcopy(review)
        stale[150]["source_native_frame"] += 1
        with self.assertRaisesRegex(ValueError, "pixel source"):
            convert(frames, actors, stale)
        wrong_camera = copy.deepcopy(review)
        wrong_camera[150]["source_camera"] = "unrecorded_view"
        with self.assertRaisesRegex(ValueError, "pixel source"):
            convert(frames, actors, wrong_camera)
        fake = copy.deepcopy(actors)
        fake[150]["source_kind"] = "synthetic_native_sample"
        with self.assertRaisesRegex(ValueError, "original Native"):
            convert(frames, fake, review)
        absent_body = copy.deepcopy(actors)
        absent_body[150]["actors"]["emergency"].pop("native_body_xy_m")
        with self.assertRaisesRegex(ValueError, "body vertices"):
            convert(frames, absent_body, review)
        no_readback = copy.deepcopy(actors)
        no_readback[180].pop("ego_brake_observed")
        with self.assertRaisesRegex(ValueError, "brake readback"):
            convert(frames, no_readback, review)
        scratch_root = Path(__file__).resolve().parents[3] / ".runtime-work"
        scratch_root.mkdir(parents=True, exist_ok=True)
        scratch = Path(tempfile.mkdtemp(prefix="C405647-original-converter-test-",
                                        dir=scratch_root))
        try:
            for name, rows in (("video_frames.jsonl", frames),
                               ("observed-actors.jsonl", actors)):
                (scratch / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
            (scratch / "emergency_review.json").write_text(json.dumps({
                "assignment_id": request(CASES[0])["assignment_id"],
                "review_kind": "original_source_review", "frame_annotations": review,
            }) + "\n")
            (scratch / "native-request.json").write_text(json.dumps(request(CASES[0])) + "\n")
            exact = request(CASES[0])
            (scratch / "scene.xodr").write_text(exact["source_map"] + "\n")
            map_hash = hashlib.sha256(exact["source_map"].encode()).hexdigest()
            (scratch / "native-map-readback.json").write_text(json.dumps({
                "requested_map_sha256": map_hash,
                "original_opendrive_sha256": map_hash,
                "initial_road_id": exact["road_id"]}) + "\n")
            capture_report = {"case_id": exact["case_id"], "frames": 600,
                              "expected_frames": 600, "error": None,
                              "accepted": False, "restoration": {"restored": True}}
            (scratch / "native-capture-report.json").write_text(json.dumps(capture_report) + "\n")
            result = process(scratch)
            self.assertEqual(result["rows"], 600)
            self.assertEqual(result["case_id"], request(CASES[0])["case_id"])
            self.assertIn("native-capture-report.json", result["capture_audit_sources"])
            self.assertEqual(len((scratch / "approach_trace.jsonl").read_text().splitlines()), 600)
            (scratch / "approach_trace.jsonl").unlink()
            failed_report = copy.deepcopy(capture_report)
            failed_report["restoration"] = {"restored": False}
            (scratch / "native-capture-report.json").write_text(json.dumps(failed_report) + "\n")
            with self.assertRaisesRegex(ValueError, "restoration did not pass"):
                process(scratch)
            (scratch / "native-capture-report.json").write_text(json.dumps(capture_report) + "\n")
            (scratch / "native-request.json").write_text(json.dumps(request(CASES[1])) + "\n")
            wrong = json.loads((scratch / "native-request.json").read_text())
            wrong["case_id"] = request(CASES[0])["case_id"]
            (scratch / "native-request.json").write_text(json.dumps(wrong) + "\n")
            with self.assertRaisesRegex(ValueError, "differs from exact construction"):
                process(scratch)
            (scratch / "native-request.json").write_text(json.dumps(request(CASES[0])) + "\n")
            (scratch / "observed-actors.jsonl").unlink()
            with self.assertRaisesRegex(ValueError, "Missing original source"):
                process(scratch)
        finally:
            shutil.rmtree(scratch)


if __name__ == "__main__":
    unittest.main()
