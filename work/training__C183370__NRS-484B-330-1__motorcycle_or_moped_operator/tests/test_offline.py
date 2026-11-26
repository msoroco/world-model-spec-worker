import unittest
from check_requests import check_pair,read_case
class FlaggedConstruction(unittest.TestCase):
 def test_exact_pair(self):
  self.assertEqual(check_pair()["crossing_frames"],[1350,1200])
 def test_each_case(self):
  self.assertEqual(len(read_case("probe_a")[1]),600)
  self.assertEqual(len(read_case("probe_b")[1]),600)
  self.assertEqual(check_pair(pair=("probe_c","probe_d"))["crossing_frames"],[1350,1200])
  self.assertEqual(len(read_case("probe_c")[1]),600)
  self.assertEqual(len(read_case("probe_d")[1]),600)
