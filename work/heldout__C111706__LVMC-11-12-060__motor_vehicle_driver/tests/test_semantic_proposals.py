"""Source-bound canonical stage chain for the exact C111706 case set."""

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from shutil import copytree


ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate


class SemanticProposalsTest(unittest.TestCase):
    def test_exact_chain(self):
        assignment = json.loads((ROOT / 'inputs' / FOLDER.name / 'assignment.json').read_text())
        manifest = json.loads((FOLDER / 'first-provisional-manifest.json').read_text())
        result = validate(FOLDER, assignment, manifest)
        self.assertEqual(result['selected_cases'], 4)
        self.assertEqual(result['stage_count'], 7)

    def test_stale_stage_hash_rejected(self):
        assignment = json.loads((ROOT / 'inputs' / FOLDER.name / 'assignment.json').read_text())
        manifest = json.loads((FOLDER / 'first-provisional-manifest.json').read_text())
        with TemporaryDirectory() as temp:
            copytree(FOLDER / 'proposals', Path(temp) / 'proposals')
            target = Path(temp) / 'proposals/template.json'
            target.write_text(target.read_text() + '\n')
            with self.assertRaisesRegex(ValueError, 'source hash changed'):
                validate(temp, assignment, manifest)


if __name__ == '__main__':
    unittest.main()
