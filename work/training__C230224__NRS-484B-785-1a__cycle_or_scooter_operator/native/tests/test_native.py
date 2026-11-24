import unittest
import runner

class TestNative(unittest.TestCase):
    def test_contract(self):
        self.assertEqual(runner.config_check()['law_id'], 'NRS-484B-785-1a')
        self.assertEqual(runner.COUNT, 600)

if __name__ == '__main__': unittest.main()
