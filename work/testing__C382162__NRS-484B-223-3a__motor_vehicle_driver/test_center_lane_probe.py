import unittest

from center_lane_probe import measure, measure_exact, validate_site
from test_center_lane_site import packet


class CenterLaneProbeTests(unittest.TestCase):
    def site(self):
        return dict(highway_source="map/highway.json", center_lane_id="shared",
                    center_lane_source="map/lane.json", one_shared_center_lane=True,
                    turns_only_both_directions=True, intersection_id="junction-A",
                    junction_kind="street", ego_id="ego")

    def frames(self, turn=True):
        return [dict(original_frame=i, time_s=i * 0.05, lane_id=lane,
                     road_id="highway", maneuver="left_turn" if i == 2 and turn else "travel",
                     source_ref="native/route.json", driver_id="ego")
                for i, lane in ((1, "approach"), (2, "shared"), (3, "departure"))]

    def purpose(self, name="left_turn_from_highway"):
        return dict(declared_purpose=name, source_ref="plan/intent.json",
                    declared_before_frame=0)

    def test_turn_and_purpose_are_separate(self):
        m = measure(self.site(), self.frames(), self.purpose())
        self.assertEqual(m["center_lane_occupancy_frames"], [2])
        self.assertTrue(m["route_matches_declared_left_turn"])
        self.assertEqual(m["purpose_sufficiency"], "unresolved")
        self.assertFalse(measure(self.site(), self.frames(False), self.purpose())["route_matches_declared_left_turn"])
        self.assertFalse(measure(self.site(), self.frames(), self.purpose("other"))["route_matches_declared_left_turn"])

    def test_both_left_turn_directions(self):
        for purpose in ("left_turn_onto_highway", "left_turn_from_highway"):
            self.assertEqual(measure(self.site(), self.frames(), self.purpose(purpose))["declared_purpose"], purpose)

    def test_reject_nonshared_lane_and_alley(self):
        site = self.site()
        site["turns_only_both_directions"] = False
        with self.assertRaisesRegex(ValueError, "single shared"):
            validate_site(site)
        site = self.site()
        site["junction_kind"] = "alley"
        with self.assertRaisesRegex(ValueError, "alley"):
            validate_site(site)

    def test_reject_missing_or_late_purpose(self):
        with self.assertRaisesRegex(ValueError, "purpose"):
            measure(self.site(), self.frames(), dict(declared_purpose="other", source_ref="", declared_before_frame=0))
        purpose = self.purpose()
        purpose["declared_before_frame"] = 2
        with self.assertRaisesRegex(ValueError, "before"):
            measure(self.site(), self.frames(), purpose)

    def test_reject_missing_occupancy_and_route_source(self):
        frames = self.frames()
        frames[1]["lane_id"] = "ordinary"
        with self.assertRaisesRegex(ValueError, "occupancy"):
            measure(self.site(), frames, self.purpose())
        frames = self.frames()
        frames[1]["source_ref"] = ""
        with self.assertRaisesRegex(ValueError, "original route"):
            measure(self.site(), frames, self.purpose())

    def test_exact_original_onto_from_purpose_and_alley(self):
        for kind in ("turn_from_highway", "turn_onto_highway", "through_travel",
                     "right_turn_purpose", "alley_junction_rejection"):
            site = packet(kind)
            route = site["route"]
            maneuver = "right_turn" if kind == "right_turn_purpose" else (
                "travel" if kind == "through_travel" else "left_turn")
            frames = [dict(original_frame=10 + i, time_s=i * .05, lane_id=lane,
                           road_id=road, maneuver=maneuver if i == 2 else "travel",
                           source_ref="sealed/original-route.json", driver_id="ego")
                      for i, (lane, road) in enumerate((
                          ("E", route["approach_road_id"]),
                          ("C", "H"), ("S", route["departure_road_id"]))) ]
            purpose = dict(declared_purpose={"turn_from_highway": "left_turn_from_highway",
                                             "turn_onto_highway": "left_turn_onto_highway",
                                             "through_travel": "through_travel",
                                             "right_turn_purpose": "right_turn",
                                             "alley_junction_rejection": "left_turn_from_alley"}[kind],
                           source_ref="sealed/pre-entry-intent.json",
                           declared_before_frame=9)
            result = measure_exact(site, kind, frames, purpose)
            self.assertEqual(result["center_lane_occupancy_frames"], [11])
            self.assertEqual(result["purpose_sufficiency"], "unresolved")
            self.assertIsNone(result["legal_judgment"])
            self.assertEqual(result["intersection_eligible"], kind != "alley_junction_rejection")
            late = dict(purpose, declared_before_frame=11)
            with self.assertRaisesRegex(ValueError, "before lane entry"):
                measure_exact(site, kind, frames, late)


if __name__ == "__main__":
    unittest.main()
