"""Portable exact-case tests run both in work and materialized construction."""
import json
import pathlib
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bus_location import inside
import runner


class BundleTest(unittest.TestCase):
    def test_selected_construction(self):
        config=json.loads((ROOT/'config.json').read_text())
        scene=runner.check()
        self.assertEqual(config['selected_case_id'],scene['case_id'])
        self.assertEqual(config['case']['location_relation'],scene['location_relation'])
        self.assertEqual(len(config['cameras']),4)
        self.assertEqual(config['rate_hz'],20)
        self.assertEqual(config['duration_s'],45)

    def test_inside_outside_polygon_geometry(self):
        polygon=[[-42,-8],[-18,-8],[-18,0],[-42,0]]
        self.assertTrue(inside([-30,-4],polygon))
        self.assertFalse(inside([-30,-12],polygon))

    def test_no_unreviewed_native_entry(self):
        import native_capture
        with self.assertRaisesRegex(ValueError,'unknown stop location'):
            native_capture.requested_hold({},'not-reviewed')


if __name__=='__main__':unittest.main()
