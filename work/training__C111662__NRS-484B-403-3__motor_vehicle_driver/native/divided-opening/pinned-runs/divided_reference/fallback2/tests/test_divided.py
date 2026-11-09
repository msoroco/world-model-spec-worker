import json
import sys
import unittest
from pathlib import Path

root=Path.cwd()
native=root/'work'/'training__C111662__NRS-484B-403-3__motor_vehicle_driver'/'native'
sys.path.insert(0,str(native))
from divided_opening import check,measure
from prove_original_divided import prove

class DividedOpening(unittest.TestCase):
    def setUp(self):
        self.bundle=native/'divided-opening'/'drafts'/'divided_reference'/'fallback2'

    def test_exact_source_bound_request(self):
        result=check(self.bundle)
        self.assertEqual(result['frames'],800)
        self.assertFalse(result['delivery_ready'])

    def test_synthetic_crossing_measurement(self):
        result=measure(self.bundle)
        self.assertEqual(result['crossing_in_authored_opening'],False)
        self.assertFalse(result['original_native_observed'])

    def test_median_and_opening_topology(self):
        xml=(self.bundle/'divided-highway.xodr').read_text()
        self.assertIn('type="median"',xml)
        self.assertIn('type="broken"',xml)
        self.assertEqual(xml.count('<road id='),3)

    def test_original_processor_synthetic_source_shape(self):
        result=prove(self.bundle)
        self.assertEqual(result['positive_count'],1)
        self.assertEqual(result['negative_count'],7)
        self.assertFalse(result['original_native_observed'])
        self.assertFalse(result['delivery_ready'])
