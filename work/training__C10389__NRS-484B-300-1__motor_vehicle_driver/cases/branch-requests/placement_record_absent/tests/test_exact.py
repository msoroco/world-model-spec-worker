"""Exact placement source preflight."""
import json
from pathlib import Path
import unittest
from placement_check import check
HERE=Path(__file__).resolve().parents[1]
class ExactPlacement(unittest.TestCase):
 def test_source(self):
  result=check(HERE)
  self.assertEqual(result['frames'],600)
  self.assertIs(result['official_placement_verified'],False)
  self.assertIs(result['original_native_observed'],False)
if __name__=='__main__':unittest.main()
