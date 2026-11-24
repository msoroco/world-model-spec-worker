"""CPU checks for exact saved Native recording projection."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from canonical_evidence import project, build_result
from native_crosswalk_capture import CAMERAS, FRAME_COUNT, NativeCrosswalkRecorder
from test_native_crosswalk_capture import ACTORS, CASE, context, observations


class CanonicalEvidenceTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        recorder = NativeCrosswalkRecorder(case_id=CASE, context=context(), actor_ids=ACTORS)
        for index in range(FRAME_COUNT):
            frame = 40 + index
            recorder.append(world_frame=frame, actors=observations(frame, index / 10),
                            camera_frames={name: SimpleNamespace(frame=frame) for name in CAMERAS})
        recorder.write(self.root)

    def test_full_projection_keeps_original_bytes(self):
        originals = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir()}
        description, evidence, hashes = project(self.root, CASE)
        self.assertEqual(len(evidence), 9)
        self.assertEqual({c["name"] for c in description["channels"]},
                         {e["name"] for e in evidence[:6]})
        self.assertEqual(hashes, originals)
        ego = [json.loads(line) for line in
               (self.root / "canonical-evidence/ego_body_history.jsonl").read_text().splitlines()]
        self.assertEqual(len(ego), 900)
        self.assertEqual(ego[0]["value"]["center"], [0.0, 0.0])
        self.assertEqual({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in self.root.iterdir() if p.is_file()}, originals)
        with self.assertRaises(FileExistsError):
            project(self.root, CASE)

    def test_rejects_frame_map_tamper_before_projection(self):
        path = self.root / "frame-map.jsonl"
        path.write_text(path.read_text().replace('"video_frame": 0', '"video_frame": 3', 1))
        with self.assertRaisesRegex(ValueError, "sealed 900-frame"):
            project(self.root, CASE)
        self.assertFalse((self.root / "canonical-evidence").exists())

    def test_native_result_schema_and_recording_evidence(self):
        for name in CAMERAS:
            (self.root / (name + ".mkv")).write_bytes(b"saved camera placeholder")
        checked = [{"target": name, "requested": True, "measured": True,
                    "matched": True} for name in
                   ("rear_approach_sampled", "lead_stop_sampled",
                    "pedestrian_in_polygon_sampled", "ego_full_pass_sampled")]
        media = {"case_id": CASE,
                 "frame_map_sha256": hashlib.sha256((self.root / "frame-map.jsonl").read_bytes()).hexdigest(),
                 "videos": {name: {"frames": 900, "video_sha256": hashlib.sha256(
                     (self.root / (name + ".mkv")).read_bytes()).hexdigest(),
                                    "rgb_sha256": "a" * 64} for name in CAMERAS}}
        finalized = {"case_id": CASE, "measured_values": {"frame_count": 900},
                     "target_checks": checked, "media": media}
        result = build_result(self.root, CASE, finalized)
        if not os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT"):
            raise ValueError("ignored runtime output root required before runtime import")
        sys.path.insert(0, str(HERE.parents[1] / "runtime"))
        from scenario_pipeline.worker_exchange.native_output import validate_result
        from scenario_pipeline.batch_pipeline.validation import recording_evidence
        validate_result(result)
        recording_evidence(result, result["recording_description"],
                           lambda name: self.root / name)
        self.assertFalse(result["setup_confirmed"])
        self.assertEqual(result["source_sha256"]["overview.mkv"],
                         media["videos"]["overview"]["video_sha256"])
        self.assertTrue(all(not check["physical_cause_confirmed"]
                            for check in result["target_checks"]))
        rows = (self.root / result["trace_reference"]).read_text().splitlines()
        self.assertEqual(len(rows), 900)
        self.assertEqual(json.loads(rows[0])["frame"], 40)
        media["videos"]["overview"]["video_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "decoded camera source differs"):
            build_result(self.root, CASE, finalized)

    def test_pinned_native_attempt_validation_with_diagnostic_ffv1(self):
        for name in CAMERAS:
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                            "color=c=black:s=16x16:r=20", "-frames:v", "900", "-c:v", "ffv1",
                            str(self.root / (name + ".mkv"))], check=True)
        from saved_video_audit import _decode
        media = {"case_id": CASE,
                 "frame_map_sha256": hashlib.sha256((self.root / "frame-map.jsonl").read_bytes()).hexdigest(),
                 "videos": {name: {"video_sha256": hashlib.sha256(
                     (self.root / (name + ".mkv")).read_bytes()).hexdigest(),
                                    **_decode(self.root / (name + ".mkv"), 16, 16, 900)}
                            for name in CAMERAS}}
        checked = [{"target": name, "requested": True, "measured": True,
                    "matched": True} for name in
                   ("rear_approach_sampled", "lead_stop_sampled",
                    "pedestrian_in_polygon_sampled", "ego_full_pass_sampled")]
        result = build_result(self.root, CASE,
                              {"case_id": CASE, "measured_values": {"frame_count": 900},
                               "target_checks": checked, "media": media})
        (self.root / "result.json").write_text(json.dumps(result) + "\n")
        if not os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT"):
            raise ValueError("ignored runtime output root required before runtime import")
        sys.path.insert(0, str(HERE.parents[1] / "runtime"))
        from scenario_pipeline.batch_pipeline.carla import validate_attempt
        validated = validate_attempt(self.root.resolve(),
                                     {"case": {"case_id": CASE},
                                      "cell": {"cell_id": "C229023"},
                                      "actor": "motor_vehicle_driver"},
                                     {"recording_description": result["recording_description"]},
                                     {"recorded_exit_code": 0}, {})
        self.assertTrue(validated["rebuild_required"])
        self.assertEqual(len(validated["video_validation"]), 4)


if __name__ == "__main__":
    unittest.main()
