"""CPU tests for the source-bound projection into native Core files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from rail_core_projection import project


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        scratch = root.parents[1] / ".runtime-work" / "c410753-projection-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.attempt = Path(self.temporary.name)
        source = json.loads((root / "cases/clear_view_16mph/construction.json").read_text())
        (self.attempt / "construction.json").write_text(json.dumps(source))
        config = next(f["content"] for f in source["files"] if f["path"] == "config.json")
        (self.attempt / "config.json").write_text(config)
        self.case_id = source["case_id"]
        frames = []
        cameras = []
        for index in range(900):
            frames.append({"original_frame": index, "time_s": index / 20,
                           "route_station_m": index / 10, "speed_mps": 5.0,
                           "position_xy_m": [index / 10, 0.0],
                           "body_on_crossing": 400 <= index < 450,
                           "flagman_on_duty": False, "signal_installed": False,
                           "signal_clearly_visible": False,
                           "signal_immediate_train_approach": False})
            cameras.append({"original_frame": index,
                            "sources": {name: {"sha256": "0" * 64}
                                        for name in ("overview", "approach",
                                                     "reference_corner", "driver_reference")}})
        (self.attempt / "native-rail-frames.json").write_text(json.dumps(frames))
        (self.attempt / "native-rail-camera-map.json").write_text(json.dumps(cameras))
        (self.attempt / "native-rail-receipt.json").write_text(json.dumps({
            "frames": {"path": "native-rail-frames.json",
                       "sha256": hashlib.sha256((self.attempt / "native-rail-frames.json").read_bytes()).hexdigest()},
            "camera_map": {"path": "native-rail-camera-map.json",
                           "sha256": hashlib.sha256((self.attempt / "native-rail-camera-map.json").read_bytes()).hexdigest()},
            "packet": {"sha256": "1" * 64}}))
        for name in ("overview", "approach", "reference_corner", "driver_reference"):
            (self.attempt / (name + ".mkv")).write_bytes(b"diagnostic-only-video-reference")
        self.packet = {"original_map_source": {"sha256": "2" * 64}}
        self.observation = {"traversal_speed_mph_max": 11.2}

    def test_projection_writes_900_joined_rows_and_never_claims_physical_acceptance(self):
        result = project(self.attempt, self.packet, self.case_id, self.observation)
        self.assertEqual(len((self.attempt / "trace.jsonl").read_text().splitlines()), 900)
        self.assertEqual(len((self.attempt / "video_frames.jsonl").read_text().splitlines()), 900)
        self.assertFalse(result["setup_confirmed"])
        self.assertFalse(result["maneuver_completed"])
        self.assertFalse(result["target_checks"][0]["physical_cause_confirmed"])
        self.assertEqual(result["case_id"], self.case_id)
        with self.assertRaisesRegex(ValueError, "already exists"):
            project(self.attempt, self.packet, self.case_id, self.observation)

    def test_camera_frame_join_mismatch_fails(self):
        path = self.attempt / "native-rail-camera-map.json"
        rows = json.loads(path.read_text())
        rows[12]["original_frame"] = 18
        path.write_text(json.dumps(rows))
        receipt = json.loads((self.attempt / "native-rail-receipt.json").read_text())
        receipt["camera_map"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        (self.attempt / "native-rail-receipt.json").write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "identity differs"):
            project(self.attempt, self.packet, self.case_id, self.observation)


if __name__ == "__main__":
    unittest.main()
