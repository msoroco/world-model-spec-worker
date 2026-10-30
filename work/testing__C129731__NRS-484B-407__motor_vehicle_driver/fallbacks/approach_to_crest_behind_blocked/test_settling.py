import tempfile,unittest,json
from pathlib import Path
import analyze
class VisibilityTests(unittest.TestCase):
 def test_two_directions_and_500ft_range(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);rows=[{'frame':1,'route_distance_m':152.4,'approach':a,'clear_ray':False} for a in ['ahead_opposing','behind_same_direction']]
   (p/'visibility_samples.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
   v=analyze.visibility_500ft(p);self.assertEqual(len(v['within_500ft_samples']),2);self.assertEqual(v['500ft_m'],152.4)
   (p/'visibility_samples.jsonl').unlink()
   with self.assertRaisesRegex(ValueError,'Missing required source: visibility_samples.jsonl'):analyze.visibility_500ft(p)

import unittest

class StartupSettlingFallbackTest(unittest.TestCase):
    def test_stationary_native_warmup(self):
        import runner
        self.assertEqual(runner.startup_settling_ticks(), 40)
