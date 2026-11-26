import unittest

import runner


class Bundle(unittest.TestCase):
    def test_native_preflight_without_carla(self):
        result = runner.check()
        self.assertTrue(result["passed"])
        self.assertEqual(result["frames"], 600)
        self.assertEqual(len(result["cameras"]), 4)
        self.assertFalse(result["carla_imported"])
        self.assertFalse(result["physical_acceptance_claimed"])


if __name__ == "__main__":
    unittest.main()
