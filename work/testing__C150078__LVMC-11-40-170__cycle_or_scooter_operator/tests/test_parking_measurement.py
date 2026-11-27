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
from parking_native import classify_observed_placement,placement_position


class SourceGateTests(unittest.TestCase):
    def test_all_exact_cases_exist_and_are_distinct(self):
        self.assertEqual(len(CASE_SPEC),8)
        if (ROOT/'case-plan.json').is_file():
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

    def test_device_parking_motion_reaches_station(self):
        self.assertAlmostEqual(placement_position([0,0],[3,0],0)[0],.15)
        self.assertEqual(placement_position([0,0],[3,0],19),[3,0])
        self.assertEqual(placement_position([0,0],[3,0],20),[3,0])

    def test_actual_placement_geometry_not_requested_label(self):
        records={'device':{'body_width_m':.8},'street':{'roadway_polygon_xy':[[0,0],[30,0],[30,5],[0,5]]},
                 'sidewalk':{'extent_polygon_xy':[[0,5],[30,5],[30,15],[0,15]]},
                 'rack':{'rack_extent_polygon_xy':[[8,8],[10,8],[10,10],[8,10]]},
                 'curb':{'curb_line_xy':[[0,5],[30,5]]},
                 'building':{'facade_line_xy':[[0,15],[30,15]]}}
        site={'requested':{'placement':'sidewalk_rack'}}
        for point_xy,expected in [([9,9],'sidewalk_rack'),([22,14.5],'sidewalk_building'),
                                  ([22,5.5],'sidewalk_curb'),([22,4.5],'roadway_curb'),
                                  ([22,17],'other_street_location')]:
            self.assertEqual(classify_observed_placement(point_xy,records,site),expected)

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
