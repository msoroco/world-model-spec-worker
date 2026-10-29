import unittest
from analyze import signed_offsets
class TurnTest(unittest.TestCase):
 def test_all_vertices(self):
  self.assertEqual(signed_offsets([1,0],[0,0],[[0,1],[0,2],[0,-1],[0,0]]),[1,2,-1,0])
