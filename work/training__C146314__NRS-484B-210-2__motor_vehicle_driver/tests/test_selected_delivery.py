"""CPU package tests over the canonical exact-case handoff."""
import json
import sys
import unittest
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
REPO = FOLDER.parents[1]
sys.path[:0] = [str(FOLDER), str(REPO / 'runtime/pipeline'),
                str(REPO / 'runtime/pipeline/scenario_pipeline')]

import runner
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case
from scenario_pipeline.worker_exchange.physical_preparation import validate as validate_physical


class SelectedDeliveryTest(unittest.TestCase):
    def test_exact_pair_and_fallbacks(self):
        self.assertEqual(runner.check()['cases'], 2)
        self.assertEqual(runner.check()['fallbacks'], 6)

    def test_cpu_contract_receipts_are_explicit_mocks(self):
        manifest = json.loads((FOLDER / 'execution-manifest.json').read_text())
        self.assertEqual({e['case_id'] for e in manifest['cases']},
                         {FOLDER.name + '__reference', FOLDER.name + '__contrast'})
        for entry in manifest['cases']:
            with self.subTest(case=entry['case_id']):
                validate_physical(REPO, FOLDER, entry)
                validate_case(FOLDER, entry, ['full-train'])
                receipt = json.loads((FOLDER / entry['physical_preparation']['receipt']).read_text())
                self.assertTrue(receipt['unit_mock'])
                self.assertFalse(receipt['original_carla_executed'])
                self.assertFalse(receipt['physical_acceptance_claimed'])
                self.assertEqual(len(receipt['fixtures']), 3)
                self.assertTrue(all(item['mock_only'] for item in receipt['fixtures']))
                self.assertFalse(entry['delivery_acceptance']['original_native_observed'])


if __name__ == '__main__':
    unittest.main()
