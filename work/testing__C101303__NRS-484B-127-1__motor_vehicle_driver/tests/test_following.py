import unittest
import json
import tempfile
from pathlib import Path

from following import choose_crest, lane_change_schedule, measure_following, finalize_saved


class FollowingTests(unittest.TestCase):
    def test_crest_requires_measured_rise_and_fall(self):
        def lane(x):
            return [dict(x=x, z=z, road_id=7, driving=True) for z in (0, 0.6, 0)]
        self.assertEqual(choose_crest([{"initial_lane": lane(0), "target_lane": lane(3.5)}])["initial_lane"][1]["z"], 0.6)
        with self.assertRaisesRegex(ValueError, "hill crest"):
            choose_crest([{"initial_lane": lane(0), "target_lane": lane(8)}])

    def test_schedule_preserves_following_before_lane_change(self):
        self.assertTrue(lane_change_schedule(5.95)["following_window"])
        self.assertEqual(lane_change_schedule(6)["ego_lane"], "target")

    def test_measurement_keeps_observation_separate_from_judgment(self):
        rows = [dict(frame=i, time_s=i / 20, ego_lane_id=1, lead_lane_id=1,
                     ego_front_s_m=10 + i, lead_rear_s_m=25 + i,
                     ego_speed_mps=10, lead_speed_mps=10) for i in range(3)]
        result = measure_following(rows)
        self.assertEqual(result["minimum_observed_gap_m"], 15)
        self.assertIsNone(result["legal_judgment"])
        rows[1]["lead_lane_id"] = 2
        with self.assertRaisesRegex(ValueError, "same-lane"):
            measure_following(rows)
        rows[1]["lead_lane_id"] = 1
        rows[1]["frame"] = 4
        with self.assertRaisesRegex(ValueError, "Nonconsecutive"):
            measure_following(rows)

    def test_saved_finalizer_binds_original_sources_and_rejects_missing_context(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            actor = dict(frame=0, time_s=0, ego_lane_id=1, lead_lane_id=1,
                         ego_front_s_m=10, lead_rear_s_m=25,
                         ego_speed_mps=10, lead_speed_mps=10)
            (root / "actor_states.jsonl").write_text(json.dumps(actor) + "\n")
            (root / "video_frames.jsonl").write_text(json.dumps({"carla_frame": 0, "time_s": 0}) + "\n")
            (root / "road_profile.json").write_text(json.dumps({"public_highway_evidence": "fixture road dedication record"}))
            (root / "surface_context.json").write_text(json.dumps({"condition": "dry"}))
            (root / "traffic_context.json").write_text(json.dumps({"participants": ["lead"]}))
            report = finalize_saved(root)
            self.assertEqual(report["minimum_observed_gap_m"], 15)
            self.assertEqual(len(report["source_sha256"]), 5)
            (root / "surface_context.json").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source: surface_context.json"):
                finalize_saved(root)


if __name__ == "__main__":
    unittest.main()
