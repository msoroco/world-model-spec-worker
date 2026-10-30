import json,tempfile,unittest
from pathlib import Path
import analyze
class EntranceMeasurements(unittest.TestCase):
 def test_nearest_is_sampled_not_continuous(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'control_context.json').write_text(json.dumps({'reference_kind':'nearest_view','source':'diagnostic actual-context join'}));(p/'view_samples.jsonl').write_text(json.dumps({'frame':1,'point_xy_m':[-10,0],'distance_to_intersection_m':3,'clear_ray':True})+'\n'+json.dumps({'frame':2,'point_xy_m':[-8,0],'distance_to_intersection_m':1,'clear_ray':True})+'\n')
   self.assertEqual(analyze.nearest_visible_point(p)['frame'],2)
 def test_missing_original_history(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'Missing required source: interaction_history.jsonl'):analyze.interaction_timing(Path(d))

import unittest

class StartupSettlingFallbackTest(unittest.TestCase):
    def test_stationary_native_warmup(self):
        import runner
        self.assertEqual(runner.startup_settling_ticks(), 40)
