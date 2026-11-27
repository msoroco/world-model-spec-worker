"""Check authored geometry and source identity of two structure alternatives."""

import copy
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))

from structure_variant import request, validate


def elevation(road_xml, station):
    entries = ET.fromstring(road_xml).findall("road/elevationProfile/elevation")
    current = max((entry for entry in entries if float(entry.get("s")) <= station),
                  key=lambda entry: float(entry.get("s")))
    delta = station - float(current.get("s"))
    return sum(float(current.get(key)) * delta ** exponent
               for exponent, key in enumerate(("a", "b", "c", "d")))


class StructureVariantTest(unittest.TestCase):
    def test_distinct_structure_approaches_on_fixed_road(self):
        for kind, support_count, deck_end in (("bridge", 2, -10),
                                               ("viaduct", 5, 10)):
            for side in ("right", "left"):
                value = request(kind, side)
                self.assertEqual(validate(value)["kind"], kind)
                self.assertEqual(len(value["support_x_m"]), support_count)
                self.assertEqual(value["deck_end_x_m"], deck_end)
                self.assertAlmostEqual(elevation(value["road_opendrive"], 40), 0)
                self.assertAlmostEqual(elevation(value["road_opendrive"], 70), 4)
                self.assertAlmostEqual(elevation(value["road_opendrive"],
                                                 deck_end + 100), 4)
                self.assertAlmostEqual(elevation(value["road_opendrive"],
                                                 deck_end + 130), 0)
                self.assertFalse(value["physical_structure_verified"])

    def test_support_and_lane_tampering_rejected(self):
        original = request("viaduct", "left")
        no_pier = copy.deepcopy(original)
        no_pier["support_x_m"].pop(2)
        with self.assertRaisesRegex(ValueError, "geometry differs"):
            validate(no_pier)
        changed_road = copy.deepcopy(original)
        changed_road["road_opendrive"] = changed_road["road_opendrive"].replace(
            'id="1" type="driving"', 'id="1" type="none"')
        changed_road["road_opendrive"] = changed_road["road_opendrive"].replace(
            'id="1"', 'id="2"')
        with self.assertRaisesRegex(ValueError, "opposed-lane"):
            validate(changed_road)


if __name__ == "__main__":
    unittest.main()
