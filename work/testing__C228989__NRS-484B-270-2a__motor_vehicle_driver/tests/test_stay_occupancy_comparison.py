"""Focused CPU checks for the three occupied-lane stay contrasts."""

import hashlib
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from comparison_audit import assess
from package_spec import AID


class StayOccupancyComparisonTests(unittest.TestCase):
    def records(self, kind):
        common = {
            "frame_count": 900, "full_decode": True, "actual_pixels": True,
            "physical_status": "unverified", "legal_verdict": None,
            "native_map_sha256": hashlib.sha256(b"original-map").hexdigest(),
            "measurements": {name: {"source": "sealed-original-placeholder"} for name in
                             ("activation", "due_care_sources", "lane_topology", "lane_movement")},
        }
        open_id = f"{AID}__{kind}_open_stay"
        occupied_id = f"{AID}__{kind}_occupied_stay"
        return {
            open_id: dict(common, case_id=open_id,
                          receipt_sha256=hashlib.sha256(open_id.encode()).hexdigest(),
                          initial_left_lane_occupied_actor_ids=[]),
            occupied_id: dict(common, case_id=occupied_id,
                              receipt_sha256=hashlib.sha256(occupied_id.encode()).hexdigest(),
                              initial_left_lane_occupied_actor_ids=["observed_lane_actor"]),
        }

    def test_each_stay_occupancy_isolates_original_traffic(self):
        for kind in ("bicycle", "electric_bicycle", "electric_scooter"):
            with self.subTest(kind=kind):
                comparison = kind + "_stay_occupancy"
                records = self.records(kind)
                reviewed = assess(comparison, records, diagnostic=True)
                self.assertEqual(reviewed["difference"], "left_lane_traffic_requested")
                self.assertFalse(reviewed["source_verified"])
                records[f"{AID}__{kind}_occupied_stay"]["initial_left_lane_occupied_actor_ids"] = []
                with self.assertRaisesRegex(ValueError, "original left-lane traffic"):
                    assess(comparison, records, diagnostic=True)


if __name__ == "__main__":
    unittest.main()
