"""CPU check of exact safety-zone geometry and construction invariants."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "native"))
from case_specs import CASES
from safety_zone_geometry import THIRTY_FEET_M, measure_frame


class SafetyZoneTest(unittest.TestCase):
    def test_boundary_and_source_requirement(self):
        zone = {"x_start_m": 80, "x_end_m": 100, "curb_y_m": -7.4,
                "zone_near_y_m": -4.5, "zone_map_source": "diagnostic",
                "curb_map_source": "diagnostic"}
        self.assertEqual(THIRTY_FEET_M, 9.144)
        for offset, expected in ((9.143, True), (9.144, True), (9.145, False)):
            # Point distance from each opposite curb end to nearest footprint edge.
            for edge in (80, 100):
                x = edge - offset if edge == 80 else edge + offset
                left = x - 2 if edge == 80 else x
                corners = [[left, -7.4], [left + 2, -7.4],
                           [left, -5.0], [left + 2, -5.0]]
                value = measure_frame(corners, zone)
                self.assertEqual(value["within_30_feet_of_opposite_end_points"], expected)
        with self.assertRaises(ValueError):
            measure_frame([[0, 0]] * 4, {**zone, "zone_map_source": None})

    def test_exact_14_cases_and_candidates(self):
        self.assertEqual(len(CASES), 14)
        for suffix in CASES:
            for candidate in ("primary", "fallback1"):
                path = ROOT / "cases" / suffix / candidate / "construction.json"
                source = json.loads(path.read_text())
                self.assertEqual(source["case_id"], ROOT.name + "__" + suffix)
                self.assertEqual(source["entrypoint"], "runner.py")
                self.assertEqual(len(source["recording_description"]["channels"]), 9)


if __name__ == "__main__":
    unittest.main()
