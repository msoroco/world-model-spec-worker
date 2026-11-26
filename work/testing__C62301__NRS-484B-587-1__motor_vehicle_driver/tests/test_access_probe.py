import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import unittest

from access_probe import measure, validate_site


class AccessProbeTests(unittest.TestCase):
    def site(self):
        return dict(authority_source="authority/access.json", highway_source="map/highway.json",
                    boundary_source="map/boundary.json", controlled_access_determination=True,
                    boundary_x_m=10.0, official_notice_source="authority/devices.json",
                    vehicle_id="ego", indicated_points=[dict(point_id="ramp-A", direction="entry",
                    y_min_m=0.0, y_max_m=2.0, device_id="sign-A",
                    device_source="native/sign-A.json", erected=True, notice_visible=True)])

    def frames(self, y=1.0):
        return [dict(original_frame=i, time_s=i * 0.05, vehicle_id="ego",
                     xy=(x, y), source_ref="native/route.json")
                for i, x in ((0, 8.0), (1, 12.0))]

    def test_indicated_and_unindicated_entry(self):
        self.assertTrue(measure(self.site(), self.frames())["all_crossings_at_indicated_points"])
        self.assertFalse(measure(self.site(), self.frames(3.0))["all_crossings_at_indicated_points"])

    def test_exit_is_separate_direction(self):
        site = self.site()
        site["indicated_points"][0]["direction"] = "exit"
        self.assertFalse(measure(site, self.frames())["all_crossings_at_indicated_points"])
        reverse = list(reversed(self.frames()))
        for i, frame in enumerate(reverse):
            frame["original_frame"] = i
            frame["time_s"] = i * 0.05
        self.assertTrue(measure(site, reverse)["all_crossings_at_indicated_points"])

    def test_requires_authority_and_erected_device(self):
        site = self.site()
        site["controlled_access_determination"] = False
        with self.assertRaisesRegex(ValueError, "status"):
            validate_site(site)
        site = self.site()
        site["indicated_points"][0]["erected"] = False
        with self.assertRaisesRegex(ValueError, "device"):
            validate_site(site)

    def test_reject_missing_route_source(self):
        frames = self.frames()
        frames[0]["source_ref"] = ""
        with self.assertRaisesRegex(ValueError, "original"):
            measure(self.site(), frames)

    def test_reject_no_crossing(self):
        frames = self.frames()
        frames[1]["xy"] = (9.0, 1.0)
        with self.assertRaisesRegex(ValueError, "not observed"):
            measure(self.site(), frames)


if __name__ == "__main__":
    unittest.main()
