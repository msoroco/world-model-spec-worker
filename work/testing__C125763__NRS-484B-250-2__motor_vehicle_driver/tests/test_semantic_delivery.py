"""Keep canonical C125763 stage hashes and exact construction joins current."""
import json
import sys
import unittest
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
REPO = FOLDER.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate  # noqa: E402


class SemanticDeliveryTests(unittest.TestCase):
    def test_all_stages_bind_exact_selected_constructions(self):
        assignment = json.loads((REPO / 'inputs' / FOLDER.name / 'assignment.json').read_text())
        manifest = json.loads((FOLDER / 'execution-manifest.json').read_text())
        receipt = validate(FOLDER, assignment, manifest)
        self.assertEqual(receipt['selected_cases'], 4)
        self.assertEqual(receipt['stage_count'], 9)


if __name__ == '__main__':
    unittest.main()
