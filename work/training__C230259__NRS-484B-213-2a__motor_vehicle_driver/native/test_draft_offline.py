import copy
import json
import unittest
from pathlib import Path
from runner import check, phase_at

class CrestRequest(unittest.TestCase):
    def setUp(self):
        self.c = json.loads(Path('config.json').read_text())
        self.road = Path('road.xodr').read_text()

    def test_exact_source_window(self):
        r=check(self.c,self.road)
        self.assertEqual(r['frames'],600)
        self.assertFalse(r['physical_verified'])
        self.assertEqual(len([phase_at(self.c,i) for i in range(600)]),600)

    def test_reject_camera_loss_and_short_controller(self):
        bad=copy.deepcopy(self.c);bad['cameras'].pop()
        with self.assertRaisesRegex(ValueError,'four synchronized'):check(bad,self.road)
        bad=copy.deepcopy(self.c);bad['control_phases'][-1]['last_frame']=598
        with self.assertRaisesRegex(ValueError,'uncovered'):check(bad,self.road)

    def test_reject_one_way_and_missing_crest(self):
        bad=copy.deepcopy(self.c);bad['road_directionality']='one_way'
        with self.assertRaisesRegex(ValueError,'two-way'):check(bad,self.road)
        with self.assertRaisesRegex(ValueError,'crest'):
            check(self.c,self.road.replace('c="-0.0002"','c="0.0002"'))

    def test_no_legal_threshold(self):
        bad=copy.deepcopy(self.c);bad['hazard_distance_legal_judgment']=50
        with self.assertRaisesRegex(ValueError,'invented'):check(bad,self.road)
