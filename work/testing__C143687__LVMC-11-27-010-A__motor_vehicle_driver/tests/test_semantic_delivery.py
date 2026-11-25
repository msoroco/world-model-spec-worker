"""Validate the exact law and selected six-case semantic chain."""
import json
from pathlib import Path
import sys
import unittest


REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'runtime' / 'scenario_pipeline'))
from worker_exchange.semantic_delivery import validate


class SemanticDeliveryTests(unittest.TestCase):
    def test_canonical_stage_chain_matches_frozen_assignment(self):
        folder = Path(__file__).resolve().parents[1]
        assignment = json.loads((REPO / 'inputs' / folder.name / 'assignment.json').read_text())
        manifest = json.loads((folder / 'execution-manifest.json').read_text())
        result = validate(folder, assignment, manifest)
        self.assertEqual(result['selected_cases'], 6)
        self.assertEqual(result['stage_count'], 10)

    def test_exception_clauses_are_exact_law_substrings(self):
        folder = Path(__file__).resolve().parents[1]
        assignment = json.loads((REPO / 'inputs' / folder.name / 'assignment.json').read_text())
        proposal = json.loads((folder / 'proposals' / 'template.json').read_text())
        clauses = [row['source_clause'] for row in proposal['structure']['exceptions']]
        self.assertEqual(len(clauses), 3)
        for clause in clauses:
            self.assertIn(clause, assignment['law']['text'])


if __name__ == '__main__':
    unittest.main()
