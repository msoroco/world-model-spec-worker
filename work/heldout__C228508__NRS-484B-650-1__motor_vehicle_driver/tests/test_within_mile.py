import importlib.util
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('within_mile_construction',ROOT/'cases/within_mile/following_construction.py')
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)


class WithinMileTests(unittest.TestCase):
    def test_physical_request_span(self):
        self.assertTrue(module.validate_schedule())
        first,second=[p for p in module.PHASES if 'closing_request' in p.label]
        self.assertLess(second.end_m-first.start_m,1609.344)
        self.assertEqual((first.start_m,first.end_m,second.start_m,second.end_m),(180,300,1050,1170))
        altered=list(module.PHASES)
        altered[2]=module.Phase(300,1750,22,18,'separate_encounters')
        altered[3]=module.Phase(1750,1870,24,11,'second_closing_request')
        altered[4]=module.Phase(1870,1900,22,18,'continue_driving')
        with self.assertRaisesRegex(ValueError,'fit within one mile'):
            module.validate_schedule(tuple(altered))
