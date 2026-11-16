import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from comparison_audit import audit


class ComparisonAuditTests(unittest.TestCase):
    def make_attempt(self, root, suffix, target, peak):
        attempt = root / suffix
        attempt.mkdir()
        case_id = ROOT.name + "__" + suffix
        config = {"selected_case_id": case_id, "law_id": "NRS-484B-600-1e",
                  "cell_id": "C10301", "actor": "motor_vehicle_driver",
                  "duration_s": 30, "fps": 20, "camera_plan": "four-source-v1",
                  "weather": "clear", "requested_speed_mph": target}
        context = {"native_map_id": "TownX", "road_id": 2, "lane_id": -1,
                   "route_source": "reviewed-route", "alley_source": "map-review",
                   "access_aisle_source": "map-review", "road_authority_source": "authority-review",
                   "subject_blueprint_id": "vehicle.test",
                   "subject_actor_id": 42}
        (attempt / "config.json").write_text(json.dumps(config))
        (attempt / "road_context.json").write_text(json.dumps(context))
        motion = [{"frame": 100 + i, "time_s": 1 + .05 * i,
                   "subject_actor_id": 42, "speed_source": "actor.get_velocity",
                   "velocity_mps": [mph * .44704, 0, 0]}
                  for i, mph in enumerate((peak - 2, peak))]
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(motion)]
        for name, rows in (("subject_motion.jsonl", motion), ("video_frames.jsonl", frames)):
            (attempt / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
        for camera in ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv"):
            (attempt / camera).write_bytes(b"test source placeholder")
        return attempt

    def make_three(self, root):
        return [self.make_attempt(root, suffix, target, peak) for suffix, target, peak in
                (("source_verified_below_80", 79, 78.9),
                 ("source_verified_at_80", 80, 79.8),
                 ("source_verified_above_80", 81, 80.6))]

    def test_comparison_records_measured_difference_without_legal_verdict(self):
        with tempfile.TemporaryDirectory() as temp:
            records = audit(self.make_three(Path(temp)))
            self.assertEqual(records["case_ids"][1].split("__")[-1], "source_verified_at_80")
            self.assertAlmostEqual(records["records"][1]["sampled_peak_mph"], 79.8)
            self.assertEqual(records["legal_conclusion"], "unresolved")
            self.assertEqual(len(records["records"][0]["sources"]), 7)

    def test_rejects_changed_fixed_route(self):
        with tempfile.TemporaryDirectory() as temp:
            attempts = self.make_three(Path(temp))
            path = attempts[2] / "road_context.json"
            context = json.loads(path.read_text())
            context["lane_id"] = -2
            path.write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, "fixed conditions differ"):
                audit(attempts)

    def test_rejects_missing_original_velocity(self):
        with tempfile.TemporaryDirectory() as temp:
            attempts = self.make_three(Path(temp))
            (attempts[1] / "subject_motion.jsonl").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source"):
                audit(attempts)

    def test_rejects_target_used_as_boundary_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            attempts = self.make_three(Path(temp))
            path = attempts[2] / "config.json"
            config = json.loads(path.read_text())
            config["requested_speed_mph"] = 79.5
            path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, "does not bracket"):
                audit(attempts)


if __name__ == "__main__":
    unittest.main()
