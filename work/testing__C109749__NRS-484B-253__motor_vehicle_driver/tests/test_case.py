import importlib.util,json,unittest,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def analysis():
    spec=importlib.util.spec_from_file_location('analyze',ROOT/'analyze.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
class Exact253(unittest.TestCase):
    def test_connected_opposing_intersection(self):
        tree=ET.parse(ROOT/'scene.xodr')
        roads={r.attrib['id']:r for r in tree.findall('road')}
        self.assertEqual(len(roads),7)
        self.assertIsNotNone(roads['13'].find('planView/geometry/arc'))
        self.assertTrue(all(roads[i].find("lanes/laneSection/left/lane[@id='1']") is not None for i in ('1','2','3','4')))
    def test_initial_yield_order_samples(self):
        polygon=[[-7,-7],[7,-7],[7,7],[-7,7]]
        rows=[
            {'frame':21714,'time_s':.05,'intersection_polygon_xy_m':polygon,'ego_body_xy_m':[[-4,0],[-4,2],[-2,0],[-2,2]],'oncoming_body_xy_m':[[1,-2],[1,0],[3,-2],[3,0]],'ego_speed_mps':.2,'oncoming_speed_mps':3.5,'ego_turn_intent':'left','ego_turn_progress':False,'ego_left_blinker':True},
            {'frame':21715,'time_s':.1,'intersection_polygon_xy_m':polygon,'ego_body_xy_m':[[-4,0],[-4,2],[-2,0],[-2,2]],'oncoming_body_xy_m':[[-2,-2],[-2,0],[0,-2],[0,0]],'ego_speed_mps':0.0,'oncoming_speed_mps':3.5,'ego_turn_intent':'left','ego_turn_progress':False,'ego_left_blinker':True},
            {'frame':21716,'time_s':.15,'intersection_polygon_xy_m':polygon,'ego_body_xy_m':[[-2,-2],[-2,0],[0,-2],[0,0]],'oncoming_body_xy_m':[[-12,-2],[-12,0],[-10,-2],[-10,0]],'ego_speed_mps':2.0,'oncoming_speed_mps':3.5,'ego_turn_intent':'left','ego_turn_progress':True,'ego_left_blinker':True},
        ]
        module=analysis()
        self.assertEqual(module.subject_interval(rows)['first_inside_time_s'],.05)
        self.assertEqual(module.opposing_interval(rows)['inside_frame_count'],2)
        sequence=module.yield_sequence(rows)
        self.assertEqual(sequence['overlap_frames'],[21714,21715])
        self.assertEqual(sequence['oncoming_clear_frame'],21716)
        self.assertEqual(sequence['ego_turn_progress_frames'],[21716])
    def test_required_source_missing(self):
        with self.assertRaisesRegex(ValueError,'Missing required source: left253_history.jsonl'):
            analysis().source(ROOT/'missing-fixture','left253_history.jsonl')
if __name__=='__main__':unittest.main()
