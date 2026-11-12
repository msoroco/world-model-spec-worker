import copy
import json
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parent.parent
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.physical_preparation import validate  # noqa: E402


class PhysicalProofTests(unittest.TestCase):
    def test_every_exact_case_has_three_outcomes_and_ordered_closure(self):
        manifest = json.loads((PACKAGE / 'execution-manifest.json').read_text())
        self.assertEqual(len(manifest['cases']), 8)
        for entry in manifest['cases']:
            validate(REPO, PACKAGE, entry)
            receipt = json.loads((PACKAGE / entry['physical_preparation']['receipt']).read_text())
            self.assertTrue(receipt['diagnostic_fixture_only'])
            self.assertFalse(receipt['physical_acceptance_claimed'])

    def test_stale_construction_binding_rejected(self):
        entry = json.loads((PACKAGE / 'execution-manifest.json').read_text())['cases'][0]
        altered = copy.deepcopy(entry)
        altered['construction_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Stale physical preparation proof'):
            validate(REPO, PACKAGE, altered)


if __name__ == '__main__':
    unittest.main()
