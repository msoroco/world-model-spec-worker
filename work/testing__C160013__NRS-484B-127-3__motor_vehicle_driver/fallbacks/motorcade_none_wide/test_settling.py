import unittest
from analyze import bounds
from runner import check
class T(unittest.TestCase):
 def test_envelope(self):self.assertEqual(bounds({'body_vertices_m':[[0,0],[1,0],[-7,0],[2,0]]}),(-7,2))
 def test_topology(self):self.assertTrue(check()['passed'])

import unittest

class StartupSettlingFallbackTest(unittest.TestCase):
    def test_stationary_native_warmup(self):
        import runner
        self.assertEqual(runner.startup_settling_ticks(), 40)
