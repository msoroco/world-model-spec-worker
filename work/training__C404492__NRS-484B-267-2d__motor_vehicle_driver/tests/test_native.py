import unittest
import runner

class TestNative(unittest.TestCase):
    def test_exact_cpu_contract(self):
        self.assertEqual(runner.config()['law_id'],'NRS-484B-267-2d')
        self.assertEqual(runner.COUNT,600)
        self.assertEqual(len(runner.CAMERAS),4)

if __name__=='__main__':unittest.main()
