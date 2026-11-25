import json
from pathlib import Path
import unittest
from runner import check, request

class DraftCase(unittest.TestCase):
    def test_exact_contract(self):
        value=check(json.loads(Path('config.json').read_text()))
        self.assertTrue(value['passed'])
        self.assertEqual(value['frames'],600)
        self.assertEqual(len(value['cameras']),4)
    def test_observed_gate_request(self):
        case=json.loads(Path('config.json').read_text())['case_id']
        observation={'ego_face':'circular_red_green_left_arrow','cross_phase':'cross_green',
                     'speed_mps':0,'front_to_stop_m':1,'entered_intersection':False,
                     'pedestrians_in_crosswalk':False,'lawful_traffic_conflict':False,
                     'completed_cycles':0}
        self.assertEqual(request(100,case,observation)['brake'],1)
        self.assertEqual(request(100,case,observation)['target_cycles'],2 if case.endswith('probe_1') else 1)
        with self.assertRaisesRegex(ValueError,'Frame'):request(600,case,observation)
    def test_wrong_identity(self):
        config=json.loads(Path('config.json').read_text())
        config['cell_id']='C999999'
        with self.assertRaisesRegex(ValueError,'identity'):check(config)

if __name__=='__main__':unittest.main()
