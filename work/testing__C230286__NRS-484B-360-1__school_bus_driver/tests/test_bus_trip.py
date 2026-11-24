import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bus_trip import ASSIGNMENT, MPH_PER_MPS, build_profile, measure


class BusTripTests(unittest.TestCase):
    def packet(self):
        return {"assignment_id": ASSIGNMENT, "original_trace_id": "synthetic-only",
                "bus_actor_id": "bus-a", "driver_actor_id": "driver-a",
                "school_bus_classification": {"qualifying_definition_branch": "synthetic-branch",
                                              "source": "synthetic-classification",
                                              "all_exclusions_reviewed": True},
                "transport_direction": "to_school", "transport_source": "synthetic-trip",
                "pupil_count": 12, "sidewalk_source": "synthetic-sidewalk",
                "frames": [{"time_s": i * 0.05, "speed_mps": 55 / MPH_PER_MPS,
                            "transporting_pupils_to_or_from_school": True} for i in range(3)]}

    def run_measure(self, packet):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "original.json"
            p.write_text(json.dumps(packet), encoding="utf-8")
            return measure(p)

    def test_profile_targets_below_at_above(self):
        for target in (54, 55, 56):
            profile = build_profile(target, 30)
            self.assertEqual(len(profile), 601)
            self.assertAlmostEqual(profile[-1]["commanded_speed_mph"], target)

    def test_exact_threshold_not_above(self):
        r = self.run_measure(self.packet())
        self.assertAlmostEqual(r["maximum_active_transport_speed_mph"], 55)
        self.assertFalse(r["active_transport_speed_above_55_mph_observed"])

    def test_above_threshold_during_trip(self):
        p = self.packet()
        p["frames"][1]["speed_mps"] = 56 / MPH_PER_MPS
        self.assertTrue(self.run_measure(p)["active_transport_speed_above_55_mph_observed"])

    def test_non_transport_speed_not_counted(self):
        p = self.packet()
        p["frames"][1]["speed_mps"] = 60 / MPH_PER_MPS
        p["frames"][1]["transporting_pupils_to_or_from_school"] = False
        self.assertFalse(self.run_measure(p)["active_transport_speed_above_55_mph_observed"])

    def test_missing_definition_exclusion_review_rejected(self):
        p = self.packet()
        p["school_bus_classification"]["all_exclusions_reviewed"] = False
        with self.assertRaisesRegex(ValueError, "exclusions"):
            self.run_measure(p)

    def test_missing_transport_phase_rejected(self):
        p = self.packet()
        del p["frames"][1]["transporting_pupils_to_or_from_school"]
        with self.assertRaisesRegex(ValueError, "transport-phase"):
            self.run_measure(p)


if __name__ == "__main__":
    unittest.main()
