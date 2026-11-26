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
                                       "outside": {"center": [13, 2.5], "heading_deg": 0,
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
        self.assertTrue(self.run_json(self.site(), construct, "outside")["wholly_outside_designated_place"])

    def test_straddling_and_touching_boundary_rejected_for_outside(self):
        for x in (11, 12):
            with self.subTest(x=x):
                site = self.site()
                site["parking_candidates"]["outside"]["center"] = [x, 2.5]
                with self.assertRaisesRegex(ValueError, "footprint"):
                    self.run_json(site, construct, "outside")

    def test_zone_enclosed_by_vehicle_rejected_for_outside(self):
        site = self.site()
        site["parking_candidates"]["outside"].update({
            "center": [5, 2.5], "length_m": 30, "width_m": 20})
        with self.assertRaisesRegex(ValueError, "footprint"):
            self.run_json(site, construct, "outside")

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
        self.assertEqual(r["stationary_wholly_inside_episodes"], [{
            "first_frame": 0, "last_frame": 2, "first_time_s": 0.0,
            "last_time_s": 0.1, "observed_span_s": 0.1}])
        self.assertEqual(r["hazard_or_congestion_status"], "unresolved")

    def test_moving_frame_not_stationary(self):
        packet = self.packet()
        packet["frames"][1]["speed_mps"] = 2
        result = self.run_json(packet, measure)
        self.assertEqual(result["stationary_wholly_inside_frames"], [0, 2])
        self.assertEqual([(x["first_frame"], x["last_frame"]) for x in result[
            "stationary_wholly_inside_episodes"]], [(0, 0), (2, 2)])

    def test_original_trace_distinguishes_overlap_from_outside(self):
        packet = self.packet()
        packet["frames"][0]["vehicle_footprint"] = [[9, 1.5], [13, 1.5], [13, 3.5], [9, 3.5]]
        packet["frames"][1]["vehicle_footprint"] = [[11, 1.5], [15, 1.5], [15, 3.5], [11, 3.5]]
        observations = self.run_json(packet, measure)["observations"]
        self.assertTrue(observations[0]["body_overlaps_place"])
        self.assertFalse(observations[0]["body_wholly_outside_place"])
        self.assertTrue(observations[1]["body_wholly_outside_place"])

    def test_missing_loading_source_rejected(self):
        packet = self.packet()
        del packet["loading_activity_source"]
        with self.assertRaisesRegex(ValueError, "loading"):
            self.run_json(packet, measure)


if __name__ == "__main__":
    unittest.main()
