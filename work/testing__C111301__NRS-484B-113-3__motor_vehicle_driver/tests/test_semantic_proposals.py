"""Pinned semantic-stage schema proof with temporary, unselected constructions."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from build_semantic_proposals import build
from scenario_pipeline.worker_exchange import semantic_delivery


class SemanticProposalTests(unittest.TestCase):
    def test_both_exact_cases_validate_with_pinned_stage_schema(self):
        built = build()
        self.assertEqual(built, {'selected_cases': 2, 'stage_count': 6})
        rows = json.loads((ROOT / 'proposals/cases.json').read_text())['cases']
        scratch = REPO / '.runtime-work'
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            folder = Path(temp)
            shutil.copytree(ROOT / 'proposals', folder / 'proposals')
            manifest = []
            for row in rows:
                if row['target_type'] == 'baseline':
                    continue
                name = row['case_id'].rsplit('__', 1)[-1] + '.json'
                (folder / name).write_text(json.dumps({
                    'recording_description': row['recording_description']}) + '\n')
                manifest.append({'case_id': row['case_id'], 'construction': name})
            assignment = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
            result = semantic_delivery.validate(folder, assignment, {'cases': manifest})
            self.assertEqual(result['stage_count'], 6)
            self.assertEqual(result['selected_cases'], 2)


if __name__ == '__main__':
    unittest.main()
