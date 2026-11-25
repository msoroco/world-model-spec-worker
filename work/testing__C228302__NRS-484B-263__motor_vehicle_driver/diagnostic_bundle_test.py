"""Bundle self-check used by the pinned offline construction command."""
import unittest

from runner import check


class BundleTest(unittest.TestCase):
    def test_exact_synthetic_exit_protocol(self):
        self.assertEqual(check()['source_kind'], 'synthetic_diagnostic_fixture')
