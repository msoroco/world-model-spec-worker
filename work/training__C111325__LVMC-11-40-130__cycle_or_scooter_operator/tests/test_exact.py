import unittest
from runner import check

class ExactBicycleConstruction(unittest.TestCase):
    def test_cpu_selected_check(self):
        result = check()
        self.assertTrue(result["passed"])
        self.assertEqual(result["frames"], 600)
        self.assertFalse(result["original_native_executed"])
