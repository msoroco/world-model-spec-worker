"""Check exact draft coverage without claiming original-source sweep completion."""
import json
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parents[1]


class SemanticProposalTests(unittest.TestCase):
    def test_exact_matrix_and_five_foot_probe(self):
        planned = json.loads((HERE / 'case-plan.json').read_text())
        proposal = json.loads((HERE / 'proposals/cases.json').read_text())
        selected = [item for item in proposal['cases'] if item['target_type'] != 'baseline']
        self.assertEqual([item['case_id'] for item in selected],
                         [item['case_id'] for item in planned['cases']])
        self.assertEqual(len(planned['comparisons']), 10)
        side = [item for item in selected if item['probe'].get('threshold_ref')]
        self.assertEqual(len(side), 6)
        self.assertEqual({item['probe']['test_value'] for item in side},
                         {1.374, 1.524, 1.674})
        self.assertEqual({item['paired_probe_id'] for item in side},
                         {'five_foot_side_gap'})
        self.assertFalse(proposal['sweeps_expanded'])
        self.assertEqual(len(proposal['sweep_specs']), 4)


if __name__ == '__main__':
    unittest.main()
