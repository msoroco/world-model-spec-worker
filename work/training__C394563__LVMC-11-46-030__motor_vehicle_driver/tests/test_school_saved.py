"""Saved source derivation tests; synthetic bytes cannot prove camera pixels."""

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from finalize import derive
from prove_school_warning import trace


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CASE = "training__C394563__LVMC-11-46-030__motor_vehicle_driver__probe_1"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class SavedSource(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        rows = trace(55, release="signal_removed")
        for row in rows:
            row["vehicle_actor_id"] = 1
            row["warning_actor_id"] = 2
            row["child_actor_id"] = 3
            row["vehicle_length_m"] = 4.0
            row["camera_native_frames"] = {name: row["native_frame"] for name in CAMERAS}
        (self.root / "native-rows.jsonl").write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n")
        frames = [{"video_frame": index, "native_frame": row["native_frame"],
                   "camera_native_frames": row["camera_native_frames"],
                   "time_s": row["time_s"] + .05} for index, row in enumerate(rows)]
        (self.root / "video_frames.jsonl").write_text(
            "\n".join(json.dumps(row) for row in frames) + "\n")
        (self.root / "road.xodr").write_text("<OpenDRIVE/>\n")
        review = {"school_pedestrian_lane_survey": True,
                  "nearest_lane_side_x_m": 0.0}
        for name in ("school_lane_source", "child_identity_source",
                     "warning_asset_source", "municipal_jurisdiction_source"):
            source = self.root / ("review-" + name)
            source.write_text(name + " fixture only\n")
            review[name + "_sha256"] = digest(source)
        (self.root / "original-school-lane-review.json").write_text(
            json.dumps(review) + "\n")
        for name in CAMERAS:
            (self.root / (name + ".mkv")).write_bytes(b"fixture-not-video")
        names = ["road.xodr", "native-rows.jsonl", "video_frames.jsonl",
                 "original-school-lane-review.json"] + [name + ".mkv" for name in CAMERAS]
        names += ["review-" + name for name in
                  ("school_lane_source", "child_identity_source",
                   "warning_asset_source", "municipal_jurisdiction_source")]
        self.seal_path = self.root / "captured-source-hashes.json"
        self.seal_path.write_text(json.dumps({"source_kind": "original_native_capture",
            "case_id": CASE, "sha256": {name: digest(self.root / name) for name in names}}) + "\n")

    def test_source_shaped_positive(self):
        measured = derive(self.root)
        self.assertEqual(measured["case_id"], CASE)
        self.assertAlmostEqual(measured["stop_distance_to_nearest_school_lane_side_ft"]["centre"], 55)
        self.assertEqual(measured["first_release_event"], "signal_removed")
        self.assertIsNone(measured["physical_completion"])

    def test_changed_native_trace_rejected(self):
        with (self.root / "native-rows.jsonl").open("a") as stream:
            stream.write("{}\n")
        with self.assertRaisesRegex(ValueError, "Changed original source"):
            derive(self.root)

    def test_missing_reviewed_child_source_rejected(self):
        (self.root / "review-child_identity_source").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source"):
            derive(self.root)

    def test_missing_camera_seal_rejected(self):
        seal = json.loads(self.seal_path.read_text())
        del seal["sha256"]["approach.mkv"]
        self.seal_path.write_text(json.dumps(seal) + "\n")
        with self.assertRaisesRegex(ValueError, "Four original cameras"):
            derive(self.root)

    def test_changed_frame_join_rejected(self):
        frames = (self.root / "video_frames.jsonl").read_text().splitlines()
        changed = json.loads(frames[100])
        changed["native_frame"] += 1
        frames[100] = json.dumps(changed)
        path = self.root / "video_frames.jsonl"
        path.write_text("\n".join(frames) + "\n")
        seal = json.loads(self.seal_path.read_text())
        seal["sha256"]["video_frames.jsonl"] = digest(path)
        self.seal_path.write_text(json.dumps(seal) + "\n")
        with self.assertRaisesRegex(ValueError, "join differs"):
            derive(self.root)


if __name__ == "__main__":
    unittest.main()
