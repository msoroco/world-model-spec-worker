import json
import unittest
from pathlib import Path
from runner import check_config
from reviewed_site import verify

class BundleTest(unittest.TestCase):
    def test_exact_config(self):
        self.assertTrue(check_config(json.loads(Path('config.json').read_text())))
    def test_original_source_gate(self):
        with self.assertRaises(ValueError):
            verify(Path('missing-reviewed-site.json'))
