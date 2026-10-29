import importlib.util,unittest,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def analysis():
    spec=importlib.util.spec_from_file_location('analyze',ROOT/'analyze.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
class NearSideStop(unittest.TestCase):
    def test_west_sign_and_no_stopline(self):
        tree=ET.parse(ROOT/'scene.xodr')
        signals=tree.findall('.//signal')
        self.assertEqual([s.attrib['id'] for s in signals],['2001'])
        self.assertEqual(tree.findall('.//object'),[])
        self.assertEqual(len(tree.findall('road')),6)
    def test_stop_motion_before_crosswalk(self):
        control={'crosswalk_upstream_x_m':-8.45,'intersection_upstream_x_m':-7}
        rows=[{'frame':1,'time_s':.05,'ego_body_xy_m':[[-14,0],[-10,2]],'ego_speed_mps':3},{'frame':2,'time_s':.1,'ego_body_xy_m':[[-14,0],[-10,2]],'ego_speed_mps':0}]
        result=analysis().stopping_sequence(control,rows)
        self.assertEqual(result['minimum_observed_speed_mps'],0)
        self.assertTrue(all(r['before_crosswalk'] for r in result['samples']))
        self.assertEqual(result['crosswalk_entry_frames'],[])
    def test_missing_case_source(self):
        with self.assertRaisesRegex(ValueError,'Missing required source: stop_history.jsonl'):
            analysis().source(ROOT/'missing-fixture','stop_history.jsonl')
if __name__=='__main__':unittest.main()
