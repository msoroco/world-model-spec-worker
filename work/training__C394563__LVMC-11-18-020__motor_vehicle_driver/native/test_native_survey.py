"""Fake-map CPU probes for Native survey paths; no CARLA execution."""
from __future__ import annotations

import unittest

from geometry import open_drive
from runner import native_survey


class FakeCarla:
    class LaneType:
        Driving = "driving"

    class Location:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z


class FakeForward:
    def __init__(self, x):
        self.x = x


class FakeTransform:
    def __init__(self, x):
        self.x = x

    def get_forward_vector(self):
        return FakeForward(self.x)


class FakeWaypoint:
    def __init__(self, lane, forward):
        self.lane_id = lane
        self.transform = FakeTransform(forward)


class FakeMap:
    def __init__(self, xml=None, reverse=False):
        self.xml = open_drive() if xml is None else xml
        self.reverse = reverse

    def to_opendrive(self):
        return self.xml

    def get_waypoint(self, location, project_to_road, lane_type):
        if project_to_road or lane_type != FakeCarla.LaneType.Driving:
            raise AssertionError("Survey must request exact driving lane")
        return FakeWaypoint(-1, -1 if self.reverse else 1) if location.y < 0 else FakeWaypoint(1, -1)


class NativeSurveyProbe(unittest.TestCase):
    def test_approach_and_opposing_lanes(self):
        observed = native_survey(FakeCarla, FakeMap())
        self.assertEqual(observed["crosswalk"]["width_along_road_m"], 3.6576)
        self.assertEqual(observed["school_xing_sign"]["x_m"], -35)
        self.assertFalse(observed["rendered_sign_text_verified"])

    def test_missing_sign_rejected(self):
        xml = open_drive().replace('name="School-Xing"', 'name="generic-warning"')
        with self.assertRaisesRegex(RuntimeError, "lost school sign"):
            native_survey(FakeCarla, FakeMap(xml))

    def test_reversed_approach_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "direction differs"):
            native_survey(FakeCarla, FakeMap(reverse=True))

    def test_yellow_marking_readback_rejected(self):
        xml = open_drive().replace('color="yellow"', 'color="white"')
        with self.assertRaisesRegex(RuntimeError, "geometry differs"):
            native_survey(FakeCarla, FakeMap(xml))


if __name__ == "__main__":
    unittest.main()
