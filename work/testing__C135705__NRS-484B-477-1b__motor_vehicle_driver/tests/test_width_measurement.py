"""Source-shaped tests for contiguous physical alley-width measurement."""
from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from width_measurement import ASSIGNMENT, continuous_free_width_m, measure

SOURCE = {"path": "reviewed/original.json", "sha256": "a" * 64}
CASE = ASSIGNMENT + "__width_9_9ft"


def body(y0, y1):
    return [[-1, y0], [11, y0], [11, y1], [-1, y1]]


def geometry():
    value = {key: SOURCE for key in (
        "public_highway_source", "city_block_source", "rear_access_source",
        "abutting_property_source", "through_connection_source", "jurisdiction_source",
        "ordinance_source", "survey_source")}
    value.update(case_id=CASE, alley_kind="other_alley", public_highway_status=True, cul_de_sac=False,
                 start_connected=True, end_connected=True, ordinance_status="unresolved",
                 cross_sections=[{"station_m": s, "left_xy_m": [s, 0],
                                  "right_xy_m": [s, 5], "source": SOURCE} for s in (0, 10)])
    return value


def history(width=1.0):
    return [{"frame": i, "time_s": i * 0.05, "source": SOURCE,
             "phase": "parked_hold" if i in (1, 2) else "approach",
             "ego_body_polygon_m": body(0, width),
             "other_body_polygons_m": []} for i in range(4)]


class AlleyWidthTests(unittest.TestCase):
    def test_occupied_edge_leaves_contiguous_width(self):
        self.assertAlmostEqual(continuous_free_width_m([0, 0], [0, 5], [body(0, 1)]), 4)

    def test_two_bodies_measure_largest_gap_not_sum(self):
        self.assertAlmostEqual(continuous_free_width_m([0, 0], [0, 5],
                               [body(0, 1), body(3, 4)]), 2)

    def test_enclosed_cross_section_is_zero(self):
        self.assertEqual(continuous_free_width_m([0, 0], [0, 5], [body(-1, 6)]), 0)

    def test_exact_10_foot_boundary(self):
        width = 5 - 10 / 3.280839895013123
        m = measure(CASE, geometry(), history(width), expected_frames=4)
        self.assertAlmostEqual(m['minimum_available_continuous_width_ft'], 10, places=5)
        self.assertFalse(m['statutory_less_than_10_ft_observed'])
        self.assertTrue(measure(CASE, geometry(), history(width + 0.1), expected_frames=4)
                        ['statutory_less_than_10_ft_observed'])

    def test_missing_original_source_rejected(self):
        rows = history()
        del rows[1]['source']
        with self.assertRaisesRegex(ValueError, 'original frame'):
            measure(CASE, geometry(), rows, expected_frames=4)

    def test_unknown_ordinance_is_not_inferred(self):
        m = measure(CASE, geometry(), history(), expected_frames=4)
        self.assertEqual(m['ordinance_applicability_judgment'], 'unresolved')

    def test_cul_de_sac_rejected(self):
        g = geometry()
        g['cul_de_sac'] = True
        with self.assertRaisesRegex(ValueError, 'connected non-cul-de-sac'):
            measure(CASE, g, history(), expected_frames=4)


if __name__ == '__main__':
    unittest.main()
