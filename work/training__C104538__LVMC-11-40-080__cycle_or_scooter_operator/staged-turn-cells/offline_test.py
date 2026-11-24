import unittest

from runner import check


class SourcePreflightTest(unittest.TestCase):
    def test_exact_staged_source(self):
        proof = check()
        self.assertTrue(proof["cpu_source_preflight_passed"])
        self.assertFalse(proof["native_capture_executed"])
