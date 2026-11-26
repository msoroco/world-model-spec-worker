"""CPU tests for saved original-source joins and missing-source rejection."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prove_observed import rows
from saved_measure import CAMERAS, analyze
from observed_left_turn import ASSIGNMENT


class SavedMeasureTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        actors = list(rows("a"))
        self.config = {
            "case_id": ASSIGNMENT + "__selected_d457f261__condition_a",
            "law_id": "NRS-484B-253", "cell_id": "C329654",
            "actor": "motor_vehicle_driver", "rate_hz": 20,
            "duration_s": 30, "duration_frames": 600,
            "cameras": [{"name": name, "width": 1920 if name == "overview" else 1280,
                         "height": 1080 if name == "overview" else 720}
                        for name in CAMERAS],
            "oncoming_conflict_s": 12.5,
            "left_signal_requested": True,
            "yield_policy": "yield_then_turn",
        }
        (self.root / "config.json").write_text(json.dumps(self.config) + "\n")
        self.actor_path = self.root / "left-turn-actors.jsonl"
        self.actor_path.write_text("".join(json.dumps(row) + "\n" for row in actors))
        self.maps = [{"video_frame": i, "native_frame": 1000 + i,
                      "camera_native_frames": {name: 1000 + i for name in CAMERAS}}
                     for i in range(600)]
        self.cameras = [{"frame": i, "native_frame": 1000 + i,
                         "rgb_sha256": {name: "a" * 64 for name in CAMERAS}}
                        for i in range(600)]
        (self.root / "road.xodr").write_text("<OpenDRIVE/>\n")
        self.write_join()

    def write_join(self):
        for name, records in (("video_frames.jsonl", self.maps),
                              ("camera-frames.jsonl", self.cameras)):
            (self.root / name).write_text("".join(json.dumps(row) + "\n" for row in records))

    def run_analysis(self):
        return analyze(self.root, self.root / "analysis.json")

    def test_source_bound_positive(self):
        report = self.run_analysis()
        self.assertEqual(report["measured"]["first_turn_progress_frame"], 300)
        self.assertEqual(len(report["sources"]), 5)
        self.assertFalse(report["actual_pixels_reviewed"])

    def test_missing_road_source(self):
        (self.root / "road.xodr").unlink()
        with self.assertRaisesRegex(ValueError, "road.xodr"):
            self.run_analysis()

    def test_camera_frame_mismatch(self):
        self.maps[300]["camera_native_frames"]["approach"] += 1
        self.write_join()
        with self.assertRaisesRegex(ValueError, "Four synchronized"):
            self.run_analysis()

    def test_missing_pixel_hash(self):
        self.cameras[300]["rgb_sha256"].pop("driver_reference")
        self.write_join()
        with self.assertRaisesRegex(ValueError, "pixel hashes"):
            self.run_analysis()

    def test_missing_subsequent_actor(self):
        actors = [json.loads(line) for line in self.actor_path.read_text().splitlines()]
        for row in actors:
            row["oncoming"].pop()
        self.actor_path.write_text("".join(json.dumps(row) + "\n" for row in actors))
        with self.assertRaisesRegex(ValueError, "subsequent opposing actors"):
            self.run_analysis()


if __name__ == "__main__":
    unittest.main()
