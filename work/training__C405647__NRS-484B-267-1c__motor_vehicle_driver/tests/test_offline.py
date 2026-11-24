import copy
import json
import unittest
from pathlib import Path
from emergency_wait import check_config,read_and_measure

class ExactEmergency(unittest.TestCase):
 def setUp(self):self.config=json.loads(Path('config.json').read_text())
 def test_scope(self):
  r=check_config(self.config,Path('emergency-road.xodr').read_text())
  self.assertEqual(r['frames'],600)
  self.assertFalse(r['actual_passing_observed'])
 def test_passage(self):
  r=read_and_measure('requested-track.jsonl','authored_native_request')
  self.assertEqual(r['requested_waits_through_whole_body_passage'],self.config['requested_release_frame']==360)
 def test_negative(self):
  for key,value in [('frames',599),('qualifying_flashes_source_required',False),('physical_completion',True)]:
   cfg=copy.deepcopy(self.config);cfg[key]=value
   with self.assertRaises(ValueError):check_config(cfg,Path('emergency-road.xodr').read_text())
  with self.assertRaises(ValueError):read_and_measure('requested-track.jsonl','original_native')
