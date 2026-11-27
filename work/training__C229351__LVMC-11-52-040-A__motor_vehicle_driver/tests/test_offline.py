import copy
import json
import unittest
from pathlib import Path
from roadside_scene import check

class ExactRoadEdge(unittest.TestCase):
 def setUp(self):
  self.config=json.loads(Path('config.json').read_text())
  self.road=Path('road-edge-road.xodr').read_text()
 def test_exact(self):
  result=check(self.config,self.road)
  self.assertEqual(result['frames'],600)
  self.assertFalse(result['original_native_observed'])
 def test_short(self):
  cfg=copy.deepcopy(self.config);cfg['duration_frames']=599
  with self.assertRaises(ValueError):check(cfg,self.road)
 def test_crosses_edge(self):
  cfg=copy.deepcopy(self.config);cfg['requested_rest_center_x_m']=6.8
  with self.assertRaises(ValueError):check(cfg,self.road)
