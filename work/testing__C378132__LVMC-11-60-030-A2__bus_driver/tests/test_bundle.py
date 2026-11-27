"""Portable exact-case tests run both in work and materialized construction."""
import json
import pathlib
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bus_location import inside, footprint_location, measure
import runner


class BundleTest(unittest.TestCase):
    def test_selected_construction(self):
        config=json.loads((ROOT/'config.json').read_text())
        scene=runner.check()
        self.assertEqual(config['selected_case_id'],scene['case_id'])
        for key in ('location_kind','loading_purpose','stop_reason','bus_class'):
            self.assertEqual(config['case'][key],scene[key])
        self.assertEqual(len(config['cameras']),4)
        self.assertEqual(config['rate_hz'],20)
        self.assertEqual(config['duration_s'],45)

    def test_designated_footprint_geometry(self):
        polygon=[[-50,-8],[-35,-8],[-35,0],[-50,0]]
        self.assertTrue(inside([-42,-4],polygon))
        self.assertFalse(inside([58,-4],polygon))
        polygons={'bus_stop':polygon}
        body=[[-45,-5],[-39,-5],[-39,-3],[-45,-3]]
        self.assertEqual(footprint_location(body,polygons),'bus_stop')
        self.assertEqual(footprint_location([[55,-5],[61,-5],[61,-3],[55,-3]],polygons),'outside')

    def test_no_unreviewed_native_entry(self):
        import native_capture
        with self.assertRaises(ValueError):
            native_capture.requested_hold({},'not-reviewed')

    def test_synthetic_packets_rejected_as_original(self):
        sample=ROOT/'cases/outside_passenger/diagnostic-refs.json'
        if not sample.is_file():
            self.skipTest('source packet fixtures live in the worker package')
        refs=json.loads(sample.read_text())
        with self.assertRaisesRegex(ValueError,'original source class unverified'):
            measure(ROOT,refs,diagnostic=False)
        measured=measure(ROOT,refs,diagnostic=True)
        self.assertEqual(measured['location_kind'],'outside')


if __name__=='__main__':unittest.main()
