import json
import unittest
from pathlib import Path
from runner import check_config
from reviewed_source import verify


class BundleTest(unittest.TestCase):
    def test_exact_config(self):
        config = json.loads(Path('config.json').read_text())
        self.assertTrue(check_config(config))

    def test_original_source_gate(self):
        config = json.loads(Path('config.json').read_text())
        with self.assertRaises(ValueError):
            verify(Path('missing-reviewed-site.json'), config['case']['variant'])
