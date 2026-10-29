import importlib.util,unittest,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def analysis():
    spec=importlib.util.spec_from_file_location('analyze',ROOT/'analyze.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
class Caravan(unittest.TestCase):
    def test_two_lanes_and_flat_public_highway(self):
        road=ET.parse(ROOT/'scene.xodr').find('road')
        self.assertIsNotNone(road.find("lanes/laneSection/right/lane[@id='-1']"))
        self.assertIsNotNone(road.find("lanes/laneSection/right/lane[@id='-2']"))
        self.assertEqual(road.attrib['junction'],'-1')
    def test_full_body_gap_and_entrant(self):
        module=analysis();rows=[{'frame':1,'time_s':.05,'follow_body_xy_m':[[0,1],[4,3]],'lead_body_xy_m':[[30,1],[34,3]],'entrant_body_xy_m':[[13,5],[17,7]],'follow_speed_mps':5,'lead_speed_mps':5,'entrant_speed_mps':5},{'frame':2,'time_s':.1,'follow_body_xy_m':[[1,1],[5,3]],'lead_body_xy_m':[[31,1],[35,3]],'entrant_body_xy_m':[[14,1],[18,3]],'follow_speed_mps':5,'lead_speed_mps':5,'entrant_speed_mps':5}]
        self.assertEqual(module.intervehicle_gap(rows)['minimum_signed_surface_gap_m'],26)
        self.assertEqual(module.entrant_occupancy(rows)['occupancy_frames'],[2])
    def test_missing_case_source(self):
        with self.assertRaisesRegex(ValueError,'Missing required source: caravan_history.jsonl'):
            analysis().source(ROOT/'missing-fixture','caravan_history.jsonl')
if __name__=='__main__':unittest.main()
