import json
import unittest
from pathlib import Path
import runner
class PilotTests(unittest.TestCase):
 def test_route_is_continuous_and_within_road(self):
  runner.check()
  for lateral in (1.75,5.25):
   points=runner.route(lateral)
   self.assertTrue(all(abs(x1-x0)<=1.5 and abs(y1-y0)<=1.5 for (x0,y0),(x1,y1) in zip(points,points[1:])))
