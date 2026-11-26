"""Comparison CPU proof uses saved-source analyzer outputs for both exact cases."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comparison_audit import audit
from observed_left_turn import ASSIGNMENT
from prove_observed import rows
from saved_measure import CAMERAS, analyze


class ComparisonAuditTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.paths = {}
        for suffix, policy, release in (("a", "yield_then_turn", 15),
                                        ("b", "turn_before_pass", 9)):
            root = Path(self.scratch.name) / suffix
            root.mkdir()
            config = {"case_id": ASSIGNMENT + "__selected_d457f261__condition_" + suffix,
                      "law_id": "NRS-484B-253", "cell_id": "C329654",
                      "actor": "motor_vehicle_driver", "rate_hz": 20,
                      "duration_s": 30, "duration_frames": 600,
                      "cameras": [{"name": name, "width": 1920 if name == "overview" else 1280,
                                   "height": 1080 if name == "overview" else 720}
                                  for name in CAMERAS],
                      "oncoming_conflict_s": 12.5, "left_signal_requested": True,
                      "yield_policy": policy, "turn_release_s": release}
            (root / "config.json").write_text(json.dumps(config) + "\n")
            actors = list(rows(suffix))
            (root / "left-turn-actors.jsonl").write_text("".join(json.dumps(row) + "\n" for row in actors))
            maps = [{"video_frame": i, "native_frame": 1000 + i,
                     "camera_native_frames": {name: 1000 + i for name in CAMERAS}}
                    for i in range(600)]
            cameras = [{"frame": i, "native_frame": 1000 + i,
                        "rgb_sha256": {name: "a" * 64 for name in CAMERAS}}
                       for i in range(600)]
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in maps))
            (root / "camera-frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in cameras))
            (root / "road.xodr").write_text("<OpenDRIVE/>\n")
            (root / "road_geometry.json").write_text(json.dumps({
                "source_kind": "synthetic_cpu",
                "intersection_polygon_xy_m": [[-7, -7], [7, -7], [7, 7], [-7, 7]]}) + "\n")
            (root / "map-survey.json").write_text(json.dumps({
                "source_kind": "synthetic_cpu", "source_sha256": "a" * 64}) + "\n")
            analysis = root / "analysis.json"
            analyze(root, analysis)
            self.paths[suffix] = analysis

    def check(self):
        return audit(self.paths["a"], self.paths["b"])

    def replace(self, suffix, field, value):
        path = self.paths[suffix]
        data = json.loads(path.read_text())
        data[field] = value
        path.write_text(json.dumps(data) + "\n")

    def test_positive_measured_contrast(self):
        result = self.check()
        self.assertEqual(result["measured_turn_frames"], [300, 180])
        self.assertFalse(result["original_native_comparison_accepted"])

    def test_fixed_camera_contract_change_rejected(self):
        changed = json.loads(self.paths["b"].read_text())
        changed["fixed_conditions"]["cameras"][0]["width"] = 1280
        self.replace("b", "fixed_conditions", changed["fixed_conditions"])
        with self.assertRaisesRegex(ValueError, "fixed conditions"):
            self.check()

    def test_missing_source_binding_rejected(self):
        changed = json.loads(self.paths["b"].read_text())
        changed["sources"].pop("left-turn-actors.jsonl")
        self.replace("b", "sources", changed["sources"])
        with self.assertRaisesRegex(ValueError, "source-bound"):
            self.check()

    def test_policy_difference_rejected(self):
        self.replace("b", "requested_turn_policy", "yield_then_turn")
        with self.assertRaisesRegex(ValueError, "deliberate turn policy"):
            self.check()

    def test_missing_measured_contrast_rejected(self):
        changed = json.loads(self.paths["b"].read_text())
        changed["measured"]["initial_opponent_passed_before_turn"] = True
        self.replace("b", "measured", changed["measured"])
        with self.assertRaisesRegex(ValueError, "passage contrast"):
            self.check()


if __name__ == "__main__":
    unittest.main()
