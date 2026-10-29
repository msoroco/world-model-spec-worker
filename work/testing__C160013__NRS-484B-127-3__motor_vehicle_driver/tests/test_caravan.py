import unittest
from analyze import bounds
class CaravanTest(unittest.TestCase):
 def test_full_body_bounds(self):self.assertEqual(bounds({"body_vertices_m":[[1,0,0],[2,0,0],[3,0,0],[4,0,0]]}),(1,4))
