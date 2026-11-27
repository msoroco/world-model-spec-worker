import json
import unittest
from pathlib import Path
from runner import check, survey_check
from finalize import measure_activation, measure_night_window

class BundleTest(unittest.TestCase):
    def test_case_and_capture(self):
        cfg=json.loads(Path('config.json').read_text())
        self.assertFalse(check(cfg)['simulation_started'])
        self.assertEqual(len(cfg['cameras']),4)
        self.assertEqual(cfg['frames'],600)
    def test_factual_methods(self):
        facts={'vehicle_over_8000_lb':True,'residence_district':True,'non_truck_route':False,'night_window':'inside'}
        self.assertFalse(measure_activation(facts)['non_truck_route'])
        self.assertFalse(measure_night_window(facts)['clock_endpoint_unresolved'])
    def test_missing_original_route(self):
        with self.assertRaisesRegex(ValueError,'Missing reviewed Native survey source'):
            survey_check({})
