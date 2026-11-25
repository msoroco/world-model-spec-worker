import unittest

from runner import check


class BundleTest(unittest.TestCase):
    def test_exact_synthetic_protocol(self):
        self.assertEqual(check()['source_kind'], 'synthetic_diagnostic_fixture')


if __name__ == '__main__':
    unittest.main()
