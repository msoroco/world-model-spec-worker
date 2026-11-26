import copy
import json
import unittest
from pathlib import Path
from taxi_loading import check_config,read_and_measure

class ExactTaxi(unittest.TestCase):
 def setUp(self):self.config=json.loads(Path('config.json').read_text())
 def test_scope(self):
  r=check_config(self.config,Path('taxi-road.xodr').read_text())
  self.assertEqual(r['frames'],600)
  self.assertFalse(r['actual_activity_observed'])
 def test_activity(self):
  r=read_and_measure('requested-track.jsonl','authored_native_request')
  self.assertEqual(r['requested_activity'],self.config['requested_activity'])
  self.assertEqual(r['active_frames'],240)
 def test_negative(self):
  for key,value in [('frames',599),('designation_source_required',False),('physical_completion',True)]:
   cfg=copy.deepcopy(self.config);cfg[key]=value
   with self.assertRaises(ValueError):check_config(cfg,Path('taxi-road.xodr').read_text())
  with self.assertRaises(ValueError):read_and_measure('requested-track.jsonl','original_native')
