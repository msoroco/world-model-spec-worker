import unittest

from inoperative_signal_probe import measure, stop_reference


class InoperativeSignalProbeTests(unittest.TestCase):
    def site(self, line=18.0, crosswalk=19.0):
        return dict(installed_signal_id="signal-A", governed_approach="north",
                    stop_line_m=line, near_crosswalk_m=crosswalk,
                    nearest_view_point_m=20.0, intersection_entry_m=22.0,
                    through_highway_source="map/road.json",
                    sightline_source="map/sight.json", ego_id="ego")

    def ego(self, operating=False):
        return [dict(original_frame=i, time_s=i * 0.05, front_m=x,
                     speed_mps=v, signal_id="signal-A", signal_uncovered=True,
                     signal_operating=operating, approach_id="north",
                     source_ref="native/ego-signal.json")
                for i, x, v in ((0, 16.0, 2.0), (1, 17.0, 0.0), (2, 23.0, 2.0))]

    def other(self, prior=0.0, within=False):
        return [dict(vehicle_id="other", original_frame=1, time_s=0.05,
                     completed_stop_time_s=prior, within_intersection=within,
                     source_ref="native/other.json")]

    def test_stop_reference_alternatives(self):
        self.assertEqual(stop_reference(self.site()), ("stop_line", 18.0))
        self.assertEqual(stop_reference(self.site(None)), ("near_crosswalk", 19.0))
        self.assertEqual(stop_reference(self.site(None, None)), ("nearest_view_point", 20.0))

    def test_source_bound_stop_and_prior_vehicle(self):
        m = measure(self.site(), self.ego(), self.other())
        self.assertEqual(m["stop_original_frame"], 1)
        self.assertEqual(m["prior_stop_or_within_intersection_vehicle_ids"], ["other"])
        self.assertEqual(m["cautious_proceeding"], "unresolved")

    def test_inoperative_at_entry_required(self):
        with self.assertRaisesRegex(ValueError, "inoperative"):
            measure(self.site(), self.ego(True), self.other())

    def test_reject_missing_sources(self):
        ego = self.ego()
        ego[0]["source_ref"] = ""
        with self.assertRaisesRegex(ValueError, "bound"):
            measure(self.site(), ego, self.other())

    def test_within_intersection_alternative(self):
        m = measure(self.site(), self.ego(), self.other(None, True))
        self.assertEqual(m["prior_stop_or_within_intersection_vehicle_ids"], ["other"])


if __name__ == "__main__":
    unittest.main()
