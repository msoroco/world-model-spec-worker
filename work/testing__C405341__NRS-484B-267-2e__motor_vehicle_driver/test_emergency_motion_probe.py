import unittest

from emergency_motion_probe import measure


class EmergencyMotionProbeTests(unittest.TestCase):
    def site(self):
        return dict(ego_id="ego", emergency_id="unit", emergency_class="authorized_emergency",
                    authorization_source="registry/unit.json",
                    qualifying_lights_source="native/lights.json",
                    light_rule_source="law/484A480.json", route_source="map/route.json",
                    officer_direction_source="native/officer.json")

    def frames(self):
        return [dict(original_frame=i, time_s=i * 0.05, ego_xy=(x, 0.0),
                     emergency_xy=(10.0 + movement, 0.0), flashing_light_on=i % 2 == 0,
                     movement_visible=visible, ego_speed_mps=3.0, ego_brake=brake,
                     officer_direction=None, motion_source="native/motion.json",
                     light_source="native/lights.json", visibility_source="native/visibility.json",
                     control_source="native/control.json")
                for i, x, movement, visible, brake in
                ((0, 0, 0, False, 0), (1, 1, 0, False, 0),
                 (2, 2, 0.2, True, 0.5), (3, 3, 0.2, True, 0.8))]

    def test_visible_movement_and_response(self):
        m = measure(self.site(), self.frames())
        self.assertEqual(m["visible_movement_original_frames"], [2])
        self.assertEqual(m["prepared_to_stop"], "unresolved")
        self.assertFalse(m["actual_stop_required_by_clause"])

    def test_reject_brake_lamps_or_visibility_flag_alone(self):
        frames = self.frames()
        for f in frames:
            f["emergency_xy"] = (10.0, 0.0)
        with self.assertRaisesRegex(ValueError, "visible actual"):
            measure(self.site(), frames)

    def test_reject_nonvisible_movement(self):
        frames = self.frames()
        frames[2]["movement_visible"] = False
        with self.assertRaisesRegex(ValueError, "visible actual"):
            measure(self.site(), frames)

    def test_officer_direction_retained(self):
        frames = self.frames()
        frames[2]["officer_direction"] = "hold"
        self.assertEqual(measure(self.site(), frames)["officer_directions"], [(2, "hold")])

    def test_reject_missing_source_and_wrong_vehicle(self):
        frames = self.frames()
        frames[2]["visibility_source"] = ""
        with self.assertRaisesRegex(ValueError, "unbound"):
            measure(self.site(), frames)
        site = self.site()
        site["emergency_class"] = "civilian"
        with self.assertRaisesRegex(ValueError, "unqualified"):
            measure(site, self.frames())


if __name__ == "__main__":
    unittest.main()
