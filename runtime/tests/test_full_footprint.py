import unittest
from worker_exchange.runtime_contract import footprint_contained
class FootprintTests(unittest.TestCase):
 def test_vertices_inside_does_not_prove_containment(self):
  road=[(0,0),(4,0),(4,4),(3,4),(3,1),(1,1),(1,4),(0,4)]
  body=[(.5,3),(3.5,3),(3.5,3.5),(.5,3.5)]
  with self.assertRaises(ValueError):footprint_contained(body,[road])
 def test_connected_surfaces_cover_full_body(self):
  body=[(.5,.2),(1.5,.2),(1.5,.8),(.5,.8)]
  self.assertTrue(footprint_contained(body,[[(0,0),(1,0),(1,1),(0,1)],[(1,0),(2,0),(2,1),(1,1)]]))
