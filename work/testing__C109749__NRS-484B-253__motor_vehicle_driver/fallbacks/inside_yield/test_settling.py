import unittest
from analyze import inside
from runner import check
class T(unittest.TestCase):
 def test_intersection(self):
  self.assertTrue(inside([[0,0],[1,1]], [[-7,-7],[7,7]]))
  self.assertFalse(inside([[20,0],[21,1]], [[-7,-7],[7,7]]))
 def test_topology(self):self.assertTrue(check()['left_turn_connected'])

import unittest

class StartupSettlingFallbackTest(unittest.TestCase):
    def test_stationary_native_warmup(self):
        import runner
        self.assertEqual(runner.startup_settling_ticks(), 40)
