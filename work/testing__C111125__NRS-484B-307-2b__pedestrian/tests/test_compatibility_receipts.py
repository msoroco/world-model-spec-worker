"""Recheck exact diagnostic Core, decode and missing-source receipts."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.package_compatibility import check_receipts


class CompatibilityReceipts(unittest.TestCase):
    def test_five_exact_positive_and_missing_source_negative(self):
        manifest = json.loads((ROOT / 'diagnostic-manifest.json').read_text())
        self.assertEqual(len(manifest['cases']), 5)
        self.assertTrue(check_receipts(REPO, ROOT, manifest))
        for entry in manifest['cases']:
            receipt = json.loads((ROOT / entry['compatibility']['receipt']).read_text())
            self.assertTrue(receipt['passed'])
            self.assertEqual(receipt['scope'], 'diagnostic software compatibility only')
            self.assertEqual(receipt['negative_removed'], 'head.json')
            self.assertIn('final_decode', receipt['checks'])
            self.assertIn('negative_case_source', receipt['checks'])


if __name__ == '__main__':
    unittest.main()
