import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'alley_site.py'
spec = importlib.util.spec_from_file_location('alley_site', MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class SiteTests(unittest.TestCase):
    def test_missing_original_site_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'site.json'
            path.write_text(json.dumps({'assignment_id': m.ASSIGNMENT, 'case_id': m.ASSIGNMENT+'__continuous_31m', 'requested_intervals_s': [[300, 2160]]}))
            with self.assertRaisesRegex(ValueError, 'source packets'):
                m.load_site(path, m.ASSIGNMENT+'__continuous_31m')

    def test_exact_intervals_cannot_be_swapped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'site.json'
            path.write_text(json.dumps({'assignment_id': m.ASSIGNMENT, 'case_id': m.ASSIGNMENT+'__continuous_31m', 'requested_intervals_s': [[300, 2100]]}))
            with self.assertRaisesRegex(ValueError, 'duration request'):
                m.load_site(path, m.ASSIGNMENT+'__continuous_31m')

    def test_polygon(self):
        square = [[0,0],[4,0],[4,4],[0,4]]
        self.assertTrue(m.inside((2,2),square))
        self.assertFalse(m.inside((5,2),square))


if __name__ == '__main__':
    unittest.main()

class PositiveSiteTests(unittest.TestCase):
    def _make(self, root):
        square = [[0,0],[8,0],[8,8],[0,8]]
        sources = {
            'map': {'opendrive_sha256':'0'*64},
            'alley': {'jurisdiction':'city','alley_status':'reviewed_original','rear_access_function':True,'cul_de_sac_excluded':True,'definition_source':'municipal-reviewed','alley_extent_polygon_xy':square},
            'designation': {'determining_office':'City Traffic Engineer','permission_status':'reviewed_original','angle_parking_permitted':True,'source':'determination-reviewed','permission_extent_polygon_xy':square},
            'marking': {'marking_status':'reviewed_original','permission_indicated':True,'content_review':'angle stalls','governed_space_polygon_xy':square,'prop_blueprint_id':'static.prop.sign','prop_pose':{'x':4,'y':4,'z':0,'yaw_deg':0}},
            'other_parking_rules': {'review_status':'reviewed_original','otherwise_lawful':True,'source':'all-other-rules-reviewed'},
            'vehicle': {'source':'vehicle-review','identity_status':'reviewed_original'},
            'prior_history': {'status':'reviewed_original_not_parked','source':'prior-history-reviewed'},
        }
        refs = {}
        for name, data in sources.items():
            path = root/(name+'.json')
            path.write_text(json.dumps(data))
            refs[name]={'path':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        site = {'assignment_id':m.ASSIGNMENT,'case_id':m.ASSIGNMENT+'__continuous_31m',
                'requested_intervals_s':[[300,2160]],'sources':refs,
                'target_xy':[4,4],'approach_xy':[20,4],'relocation_xy':[20,4],
                'map_id':'Town01','road_id':1,'vehicle_blueprint_id':'vehicle.tesla.model3',
                'approach_heading_degrees':0,'target_heading_degrees':0}
        path=root/'site.json';path.write_text(json.dumps(site))
        return path,refs

    def test_positive_review_and_changed_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            path,refs=self._make(root)
            site,records=m.load_site(path,m.ASSIGNMENT+'__continuous_31m')
            self.assertEqual(site['target_xy'],[4,4])
            self.assertEqual(records['alley']['jurisdiction'],'city')
            (root/'prior_history.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'source missing or changed'):
                m.load_site(path,m.ASSIGNMENT+'__continuous_31m')
