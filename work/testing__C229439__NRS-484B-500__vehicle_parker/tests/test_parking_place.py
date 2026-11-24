import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parking_place import ASSIGNMENT, construct, measure


class ParkingPlaceTests(unittest.TestCase):
    def site(self):
        return {"assignment_id": ASSIGNMENT, "map_id": "synthetic-map",
                "device_id": "device-a", "designated_place_id": "zone-a",
                "device_instructions_source": "synthetic-instructions",
                "official_authority_source": "synthetic-authority",
                "device_erected": True, "hazard_or_congestion_source": "synthetic-context",
                "hazard_or_congestion_status": "unresolved",
                "designated_place_polygon": [[0, 0], [10, 0], [10, 5], [0, 5]],
                "parking_candidates": {"inside": {"center": [5, 2.5], "heading_deg": 0,
                                                  "length_m": 4, "width_m": 2,
                                                  "requested_wholly_within_place": True},
                                       "outside": {"center": [12, 2.5], "heading_deg": 0,
                                                   "length_m": 4, "width_m": 2,
                                                   "requested_wholly_within_place": False}}}

    def packet(self):
        packet = self.site()
        packet.update({"original_trace_id": "synthetic-only", "vehicle_actor_id": "car-a",
                       "parker_actor_id": "person-a", "loading_activity_source": "synthetic-loading",
                       "officer_or_device_direction_source": "synthetic-directions",
                       "frames": [{"time_s": i * .05, "speed_mps": 0,
                                   "vehicle_footprint": [[3, 1.5], [7, 1.5], [7, 3.5], [3, 3.5]]}
                                  for i in range(3)]})
        return packet

    def run_json(self, value, func, *args):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "source.json"
            p.write_text(json.dumps(value), encoding="utf-8")
            return func(p, *args)

    def test_inside_and_outside_candidates(self):
        self.assertTrue(self.run_json(self.site(), construct, "inside")["wholly_within_designated_place"])
        self.assertFalse(self.run_json(self.site(), construct, "outside")["wholly_within_designated_place"])

    def test_footprint_claim_mismatch_rejected(self):
        s = self.site()
        s["parking_candidates"]["inside"]["requested_wholly_within_place"] = False
        with self.assertRaisesRegex(ValueError, "footprint"):
            self.run_json(s, construct, "inside")

    def test_missing_official_authority_rejected(self):
        s = self.site()
        del s["official_authority_source"]
        with self.assertRaisesRegex(ValueError, "official"):
            self.run_json(s, construct, "inside")

    def test_original_stationary_inside_observed(self):
        r = self.run_json(self.packet(), measure)
        self.assertEqual(r["stationary_wholly_inside_frames"], [0, 1, 2])
        self.assertEqual(r["hazard_or_congestion_status"], "unresolved")

    def test_moving_frame_not_stationary(self):
        packet = self.packet()
        packet["frames"][1]["speed_mps"] = 2
        self.assertEqual(self.run_json(packet, measure)["stationary_wholly_inside_frames"], [0, 2])

    def test_missing_loading_source_rejected(self):
        packet = self.packet()
        del packet["loading_activity_source"]
        with self.assertRaisesRegex(ValueError, "loading"):
            self.run_json(packet, measure)


if __name__ == "__main__":
    unittest.main()
