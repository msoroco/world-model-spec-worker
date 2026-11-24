import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from same_lane_pass import ASSIGNMENT, measure


class SameLanePassTests(unittest.TestCase):
    def packet(self):
        return {"assignment_id": ASSIGNMENT, "original_trace_id": "synthetic-test-only",
                "ego_vehicle_type": "motorcycle", "ego_actor_id": "moto-a", "other_actor_id": "car-b",
                "subsection_3_exception_status": "unresolved",
                "frames": [{"time_s": i * 0.05, "ego_lane_id": "lane-a", "other_lane_id": "lane-a",
                            "longitudinal_relation": ("behind", "abreast", "ahead")[i],
                            "driver_consent_observed": False, "same_lane_two_wheeler_count": 1} for i in range(3)]}

    def run_measure(self, packet):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "original.json"
            p.write_text(json.dumps(packet), encoding="utf-8")
            return measure(p)

    def test_same_lane_pass(self):
        r = self.run_measure(self.packet())
        self.assertTrue(r["same_lane_pass_observed"])
        self.assertTrue(r["same_lane_abreast_observed"])
        self.assertEqual(r["subsection_3_exception_status"], "unresolved")

    def test_different_lane_not_same_lane_pass(self):
        p = self.packet()
        p["frames"][1]["ego_lane_id"] = "lane-b"
        p["frames"][2]["ego_lane_id"] = "lane-b"
        self.assertFalse(self.run_measure(p)["same_lane_pass_observed"])

    def test_abreast_without_pass(self):
        p = self.packet()
        p["frames"][2]["longitudinal_relation"] = "abreast"
        r = self.run_measure(p)
        self.assertTrue(r["same_lane_abreast_observed"])
        self.assertFalse(r["same_lane_pass_observed"])

    def test_missing_lane_rejected(self):
        p = self.packet()
        del p["frames"][1]["other_lane_id"]
        with self.assertRaisesRegex(ValueError, "lane identities"):
            self.run_measure(p)

    def test_unknown_exception_status_rejected(self):
        p = self.packet()
        p["subsection_3_exception_status"] = "assumed_absent"
        with self.assertRaisesRegex(ValueError, "exception status"):
            self.run_measure(p)


if __name__ == "__main__":
    unittest.main()
