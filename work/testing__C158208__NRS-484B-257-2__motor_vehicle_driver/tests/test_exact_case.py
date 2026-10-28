import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
import runner
class ExactCaseTests(unittest.TestCase):
 def test_static_construction_and_route(self):
  runner.check()
  cfg,case=runner.selected()
  p=runner.path_for(cfg,case)
  self.assertGreater(len(p),20)
  self.assertEqual(cfg['selected_case_id'],case['case_id'])
 def test_authored_map_has_road_surfaces(self):
  root=ET.parse('scene.xodr').getroot()
  self.assertTrue(root.findall('road'))
