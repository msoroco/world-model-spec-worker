import unittest

from right_turn_lane_probe import measure, validate_site


class RightTurnLaneProbeTests(unittest.TestCase):
    def site(self):
        return dict(highway_source="map/highway.json", turn_lane_id="right-only",
                    turn_lane_source="map/lane.json", one_right_turn_lane=True,
                    exclusive_right_turn=True, t_junction_id="T-1",
                    entry_road_id="stem", right_exit_road_id="cross-right",
                    connected_route_source="map/route.json", ego_id="ego")

    def frames(self, turn=True):
        return [dict(original_frame=i, time_s=i * 0.05, lane_id=lane,
                     road_id=road, maneuver="right_turn" if i == 3 and turn else "travel",
                     source_ref="native/route.json", driver_id="ego")
                for i, lane, road in ((1, "approach", "stem"),
                                      (2, "right-only", "stem"),
                                      (3, "exit", "cross-right"))]

    def purpose(self, name="right_turn"):
        return dict(declared_purpose=name, source_ref="plan/intent.json", declared_before_frame=0)

    def test_bound_turn_and_purpose(self):
        m = measure(self.site(), self.frames(), self.purpose())
        self.assertEqual(m["lane_occupancy_original_frames"], [2])
        self.assertTrue(m["purpose_route_agreement"])
        self.assertEqual(m["purpose_sufficiency"], "unresolved")

    def test_mismatch_does_not_infer_purpose(self):
        self.assertFalse(measure(self.site(), self.frames(False), self.purpose())["purpose_route_agreement"])
        self.assertFalse(measure(self.site(), self.frames(), self.purpose("other"))["purpose_route_agreement"])

    def test_reject_nonexclusive_or_disconnected_lane(self):
        site = self.site()
        site["exclusive_right_turn"] = False
        with self.assertRaisesRegex(ValueError, "exclusive"):
            validate_site(site)
        site = self.site()
        site["right_exit_road_id"] = "stem"
        with self.assertRaisesRegex(ValueError, "distinct"):
            validate_site(site)

    def test_reject_late_or_unsourced_purpose(self):
        purpose = self.purpose()
        purpose["declared_before_frame"] = 2
        with self.assertRaisesRegex(ValueError, "before"):
            measure(self.site(), self.frames(), purpose)
        purpose = self.purpose()
        purpose["source_ref"] = ""
        with self.assertRaisesRegex(ValueError, "sourced"):
            measure(self.site(), self.frames(), purpose)

    def test_reject_unbound_route(self):
        frames = self.frames()
        frames[1]["source_ref"] = ""
        with self.assertRaisesRegex(ValueError, "original route"):
            measure(self.site(), frames, self.purpose())


if __name__ == "__main__":
    unittest.main()
