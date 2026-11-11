import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate


class SemanticProposalTests(unittest.TestCase):
    def test_exact_chain_and_source_hash_rejection(self):
        assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
        manifest = json.loads((HERE / 'execution-manifest.json').read_text())
        receipt = validate(HERE, assignment, manifest)
        self.assertEqual((receipt['stage_count'], receipt['selected_cases']), (7, 6))
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            shutil.copytree(HERE / 'proposals', folder / 'proposals')
            template = folder / 'proposals/template.json'
            template.write_text(template.read_text() + ' ')
            with self.assertRaisesRegex(ValueError, 'source hash changed'):
                validate(folder, assignment, manifest)


if __name__ == '__main__':
    unittest.main()
