import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from walk_signal_measurement import ASSIGNMENT, measure


class WalkSignalTests(unittest.TestCase):
    def packet(self):
        return {"assignment_id": ASSIGNMENT, "original_trace_id": "synthetic-test-only",
                "pedestrian_actor_id": "person-a", "crosswalk_id": "crosswalk-a", "pedestrian_signal_id": "ped-signal-a",
                "frames": [{"time_s": i * 0.05, "signal_indication": "walk",
                            "pedestrian_facing_signal": True, "pedestrian_in_crosswalk": i >= 2,
                            "crossing_direction_matches_signal": True,
                            "driver_actor_ids": ["car-a"], "driver_yield_observed": False} for i in range(4)]}

    def run_measure(self, packet):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "original.json"
            p.write_text(json.dumps(packet), encoding="utf-8")
            return measure(p)

    def test_permission_separate_from_driver_observation(self):
        r = self.run_measure(self.packet())
        self.assertTrue(r["walk_permission_conditions_observed"])
        self.assertFalse(r["driver_yield_observed_at_entry"])
        self.assertEqual(r["entry_bracket_indices"], [1, 2])

    def test_wait_at_entry(self):
        p = self.packet()
        p["frames"][2]["signal_indication"] = "wait"
        self.assertFalse(self.run_measure(p)["walk_permission_conditions_observed"])

    def test_wrong_direction(self):
        p = self.packet()
        p["frames"][2]["crossing_direction_matches_signal"] = False
        self.assertFalse(self.run_measure(p)["walk_permission_conditions_observed"])

    def test_missing_signal_state_rejected(self):
        p = self.packet()
        del p["frames"][2]["signal_indication"]
        with self.assertRaisesRegex(ValueError, "signal indication"):
            self.run_measure(p)

    def test_no_entry_rejected(self):
        p = self.packet()
        for f in p["frames"]:
            f["pedestrian_in_crosswalk"] = False
        with self.assertRaisesRegex(ValueError, "no observed"):
            self.run_measure(p)


if __name__ == "__main__":
    unittest.main()
