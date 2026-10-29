import unittest
from analyze import inside
class YieldTest(unittest.TestCase):
 def test_spanning_body(self):self.assertTrue(inside([[-8,-8],[8,-8],[-8,8],[8,8]],[[-7,-7],[7,-7],[7,7],[-7,7]]))
