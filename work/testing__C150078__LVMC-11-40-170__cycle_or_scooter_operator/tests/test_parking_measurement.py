import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from parking_source import ASSIGNMENT,CASE_SPEC,inside,load_site
from parking_measurement import measure


class SourceGateTests(unittest.TestCase):
    def test_all_exact_cases_exist_and_are_distinct(self):
        plan=json.loads((ROOT/'case-plan.json').read_text())
        self.assertEqual({c['case_id'].removeprefix(ASSIGNMENT+'__') for c in plan['cases']},set(CASE_SPEC))
        self.assertEqual(len(plan['cases']),len(CASE_SPEC))
        self.assertEqual(len(plan['comparisons']),3)
        self.assertEqual(plan['judgment_range_inventory'],[])

    def test_polygon_boundary(self):
        p=[[0,0],[4,0],[4,4],[0,4]]
        self.assertTrue(inside([2,2],p))
        self.assertFalse(inside([5,2],p))
        with self.assertRaises(ValueError): inside([2,float('nan')],p)

    def test_missing_original_site_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'site.json'
            path.write_text(json.dumps({'assignment_id':ASSIGNMENT,'case_id':ASSIGNMENT+'__bicycle_rack_clear','requested':{'device_class':'bicycle','placement':'sidewalk_rack','pedestrian_context':'clear'},'sources':{}}))
            with self.assertRaisesRegex(ValueError,'original site source inventory incomplete'):
                load_site(path,ASSIGNMENT+'__bicycle_rack_clear')

    def test_missing_original_acquisition_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'config.json').write_text(json.dumps({'assignment_id':ASSIGNMENT,'selected_case_id':ASSIGNMENT+'__bicycle_rack_clear'}))
            (p/'acquisition.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'Missing required source'):
                measure(p)


if __name__=='__main__': unittest.main()
