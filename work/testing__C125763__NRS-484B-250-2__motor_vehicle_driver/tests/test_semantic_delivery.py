"""Check current preliminary judgment-observable stage coverage."""
import json
import unittest
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]


class SemanticDeliveryTests(unittest.TestCase):
    def test_four_current_judgment_observable_drafts_cover_sweeps(self):
        proposal = json.loads((FOLDER / 'proposals/cases.json').read_text())
        expected = {s['judgment_refs'][0]['phrase'] for s in proposal['sweep_specs']}
        drafts = [json.loads((FOLDER / f'proposals/judgment-observables-{i}.json').read_text())
                  for i in range(1, 5)]
        self.assertEqual({d['phrase'] for d in drafts}, expected)
        for draft in drafts:
            self.assertEqual(draft['template_id'], 'NRS-484B-250-2@motor_vehicle_driver')
            self.assertTrue(draft['observable_requirements']['observables'])
            self.assertIsInstance(draft['observable_requirements']['sweep_dimensions'], list)
            self.assertEqual(draft['status'], 'draft')


if __name__ == '__main__':
    unittest.main()
