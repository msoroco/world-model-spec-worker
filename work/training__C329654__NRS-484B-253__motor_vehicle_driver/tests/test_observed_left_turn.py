"""Source-shaped CPU proof for original-frame metering rules."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from observed_left_turn import ASSIGNMENT, measure


class ObservedLeftTurnTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.path = Path(self.scratch.name) / "actors.jsonl"
        self.rows = []
        case = ASSIGNMENT + "__selected_d457f261__condition_a"
        for frame in range(600):
            time_s = frame / 20
            turn = frame >= 300
            self.rows.append({
                "case_id": case, "source_kind": "synthetic_cpu",
                "frame": frame, "native_frame": frame + 1000,
                "time_s": time_s,
                "ego": {"speed_mps": 4 if frame < 100 or turn else 0,
                        "left_turn_progress": min(1, (frame - 299) / 80) if turn else 0,
                        "distance_to_conflict_m": 5 if not turn else max(-2, 5 - (frame - 300) / 10),
                        "inside_intersection": frame >= 100,
                        "left_indicator_on": True},
                "oncoming": [
                    {"actor_id": "initial", "speed_mps": 8,
                     "distance_to_conflict_m": 100 - 8 * time_s,
                     "approach_lane_opposite": True},
                    {"actor_id": "subsequent", "speed_mps": 7 if frame < 310 else 4,
                     "distance_to_conflict_m": 140 - 7 * time_s,
                     "approach_lane_opposite": True},
                ],
            })

    def check(self):
        self.path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in self.rows))
        return measure(self.path)

    def test_complete_source_shaped_sequence(self):
        result = self.check()
        self.assertTrue(result["initial_opponent_passed_before_turn"])
        self.assertTrue(result["subsequent_opponent_decelerated_after_turn"])
        self.assertIsNone(result["legal_priority_verdict"])
        self.assertEqual(result["first_turn_progress_frame"], 300)

    def test_missing_subsequent_opponent_rejected(self):
        for row in self.rows:
            row["oncoming"].pop()
        with self.assertRaisesRegex(ValueError, "subsequent opposing actors"):
            self.check()

    def test_authored_request_cannot_be_observed_source(self):
        for row in self.rows:
            row["source_kind"] = "authored_native_request"
        with self.assertRaisesRegex(ValueError, "Observed actor source provenance"):
            self.check()

    def test_missing_original_lamp_readback_rejected(self):
        self.rows[290]["ego"].pop("left_indicator_on")
        with self.assertRaisesRegex(ValueError, "lamp readback"):
            self.check()

    def test_broken_native_frame_join_rejected(self):
        self.rows[300]["native_frame"] = self.rows[299]["native_frame"]
        with self.assertRaisesRegex(ValueError, "Native frame sequence"):
            self.check()

    def test_moving_through_without_yield_rejected(self):
        for row in self.rows:
            row["ego"]["speed_mps"] = 4
        with self.assertRaisesRegex(ValueError, "preturn yielding wait"):
            self.check()

    def test_incomplete_source_rejected(self):
        self.rows.pop()
        with self.assertRaisesRegex(ValueError, "600-frame"):
            self.check()


if __name__ == "__main__":
    unittest.main()
