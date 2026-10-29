import importlib.util,unittest,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def analysis():
    spec=importlib.util.spec_from_file_location('analyze',ROOT/'analyze.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
class MarkedLane(unittest.TestCase):
    def test_two_same_direction_marked_lanes(self):
        road=ET.parse(ROOT/'scene.xodr').find('road')
        self.assertIsNotNone(road.find("lanes/laneSection/right/lane[@id='-1']"))
        self.assertIsNotNone(road.find("lanes/laneSection/right/lane[@id='-2']"))
        self.assertEqual(road.find("lanes/laneSection/right/lane[@id='-1']/roadMark").attrib['type'],'broken')
    def test_signal_and_gap_are_separate(self):
        module=analysis();road={'lane_boundary_y_m':3.5}
        rows=[{'frame':1,'time_s':.05,'ego_body_xy_m':[[0,4],[2,4]],'target_body_xy_m':[[-8,1],[-6,1]],'ego_speed_mps':4,'target_speed_mps':5,'left_blinker':True,'driver_check_recorded':False},{'frame':2,'time_s':.1,'ego_body_xy_m':[[1,3],[3,3]],'target_body_xy_m':[[-7,1],[-5,1]],'ego_speed_mps':4,'target_speed_mps':5,'left_blinker':True,'driver_check_recorded':False}]
        signal=module.signal_before_departure(road,rows)
        self.assertEqual(signal['observed_signal_lead_s'],.05)
        self.assertEqual(module.target_lane_gap(rows)['minimum_signed_surface_gap_m'],6)
    def test_missing_case_source(self):
        with self.assertRaisesRegex(ValueError,'Missing required source: lane_change_history.jsonl'):
            analysis().source(ROOT/'missing-fixture','lane_change_history.jsonl')
if __name__=='__main__':unittest.main()
