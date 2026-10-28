import json
import unittest
from pathlib import Path
import runner
class CaseTests(unittest.TestCase):
 def test_exact_selected_geometry_and_channels(self):
  runner.check()
  cfg=json.loads(Path('config.json').read_text())
  self.assertEqual(cfg['selected_case_id'],cfg['case']['case_id'])
  self.assertEqual(cfg['law_id'],cfg['case']['target_law_id'])
 def test_route_continuity(self):
  cfg=json.loads(Path('config.json').read_text())
  points=runner.route(cfg)
  self.assertTrue(all(max(abs(a[0]-b[0]),abs(a[1]-b[1]))<=1.5 for a,b in zip(points,points[1:])))
