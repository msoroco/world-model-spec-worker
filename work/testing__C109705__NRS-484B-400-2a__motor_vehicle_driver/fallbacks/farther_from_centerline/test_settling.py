import unittest, tempfile, json
from pathlib import Path
from analyze import signed_offsets, measured_approach, measured_departure
from runner import check
class T(unittest.TestCase):
 def test_geometry(self):
  self.assertEqual(signed_offsets([1,0],[0,0],[[0,-2,0],[1,-1,0],[2,-3,0],[3,-4,0]]),[-2,-1,-3,-4])
 def test_topology(self):self.assertTrue(check()['left_turn_connected'])
 def test_missing(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaisesRegex(ValueError,'Missing required source: road_geometry.json'):measured_approach(Path(t))

import unittest

class StartupSettlingFallbackTest(unittest.TestCase):
    def test_stationary_native_warmup(self):
        import runner
        self.assertEqual(runner.startup_settling_ticks(), 40)
