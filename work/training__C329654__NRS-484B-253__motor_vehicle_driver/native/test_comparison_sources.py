"""The independent comparison rereads each saved source, not a claimed report."""
import json
import tempfile
import unittest
from pathlib import Path

from comparison_audit import audit_attempts
from prove_observed import rows
from saved_measure import CAMERAS


class ComparisonSourcesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.attempts = []
        for suffix, policy in (("a", "yield_then_turn"), ("b", "turn_before_pass")):
            folder = self.root / suffix
            folder.mkdir()
            data = list(rows(suffix))
            config = {"case_id": data[0]["case_id"], "law_id": "NRS-484B-253",
                      "cell_id": "C329654", "actor": "motor_vehicle_driver",
                      "rate_hz": 20, "duration_s": 30, "duration_frames": 600,
                      "cameras": [{"name": name} for name in CAMERAS],
                      "oncoming_conflict_s": 12.5, "left_signal_requested": True,
                      "yield_policy": policy}
            (folder / "config.json").write_text(json.dumps(config) + "\n")
            (folder / "road.xodr").write_text("<OpenDRIVE/>\n")
            (folder / "road_geometry.json").write_text(json.dumps({
                "source_kind": "synthetic_cpu",
                "intersection_polygon_xy_m": [[-7, -7], [7, -7], [7, 7], [-7, 7]]}) + "\n")
            (folder / "map-survey.json").write_text(json.dumps({
                "source_kind": "synthetic_cpu", "source_sha256": "a" * 64}) + "\n")
            (folder / "left-turn-actors.jsonl").write_text("".join(
                json.dumps(row) + "\n" for row in data))
            (folder / "video_frames.jsonl").write_text("".join(json.dumps({
                "video_frame": i, "native_frame": i + 1000,
                "camera_native_frames": {name: i + 1000 for name in CAMERAS}}) + "\n"
                for i in range(600)))
            (folder / "camera-frames.jsonl").write_text("".join(json.dumps({
                "frame": i, "native_frame": i + 1000,
                "rgb_sha256": {name: "a" * 64 for name in CAMERAS}}) + "\n"
                for i in range(600)))
            self.attempts.append(folder)

    def test_recomputed_positive(self):
        result = audit_attempts(*self.attempts)
        self.assertEqual(result["measured_initial_passage_before_turn"], [True, False])
        self.assertFalse(result["original_native_comparison_accepted"])

    def test_missing_original_source_rejected(self):
        (self.attempts[1] / "road.xodr").unlink()
        with self.assertRaisesRegex(ValueError, "road.xodr"):
            audit_attempts(*self.attempts)

    def test_changed_fixed_source_rejected(self):
        path = self.attempts[1] / "config.json"
        cfg = json.loads(path.read_text())
        cfg["oncoming_conflict_s"] = 14
        path.write_text(json.dumps(cfg) + "\n")
        with self.assertRaisesRegex(ValueError, "fixed conditions differ"):
            audit_attempts(*self.attempts)

    def test_changed_measured_actor_rejected(self):
        path = self.attempts[1] / "left-turn-actors.jsonl"
        data = [json.loads(line) for line in path.read_text().splitlines()]
        data[200]["oncoming"].pop()
        path.write_text("".join(json.dumps(row) + "\n" for row in data))
        with self.assertRaisesRegex(ValueError, "opposing actors"):
            audit_attempts(*self.attempts)

    def test_missing_subsequent_response_rejected(self):
        path = self.attempts[1] / "left-turn-actors.jsonl"
        data = [json.loads(line) for line in path.read_text().splitlines()]
        for row in data:
            row["oncoming"][1]["speed_mps"] = 7
        path.write_text("".join(json.dumps(row) + "\n" for row in data))
        with self.assertRaisesRegex(ValueError, "subsequent opposing response"):
            audit_attempts(*self.attempts)


if __name__ == "__main__":
    unittest.main()
