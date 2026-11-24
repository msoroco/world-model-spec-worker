"""Check current preliminary judgment-observable stage coverage."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
REPO = FOLDER.parents[1]


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

    def test_full_stage_chain_binds_current_exact_manifest(self):
        code = (
            "import json,pathlib,sys; "
            "sys.path.insert(0,'runtime/scenario_pipeline'); "
            "from worker_exchange import semantic_delivery; "
            "p=pathlib.Path(sys.argv[1]); "
            "a=json.loads((pathlib.Path('inputs')/p.name/'assignment.json').read_text()); "
            "m=json.loads((p/'execution-manifest.json').read_text()); "
            "print(json.dumps(semantic_delivery.validate(p,a,m)))"
        )
        output_root = REPO / '.runtime-work/c125763-semantic-test'
        output_root.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(output_root),
                   PYTHONDONTWRITEBYTECODE='1')
        completed = subprocess.run([sys.executable, '-c', code, str(FOLDER)],
                                   cwd=REPO, env=env, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result['stage_count'], 9)
        self.assertEqual(result['selected_cases'], 4)


if __name__ == '__main__':
    unittest.main()
