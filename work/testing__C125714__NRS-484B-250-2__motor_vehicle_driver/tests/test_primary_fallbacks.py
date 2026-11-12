import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.candidate_constructions import validate


def inline(construction):
    return {row['path']: row['content'] for row in construction['files']}


class PrimaryFallbackTest(unittest.TestCase):
    def test_three_proved_distinct_engineering_changes(self):
        manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
        entry = manifest['cases'][0]
        self.assertEqual(validate(ROOT, entry, 'NRS-484B-250-2', 'C125714',
                                  required=True, require_alternate=True,
                                  candidate_count=4)['fallbacks'],
                         ['fallback1', 'fallback2', 'fallback3'])
        primary = inline(json.loads((ROOT / 'construction.json').read_text()))
        original = json.loads(primary['config.json'])
        candidates = [inline(json.loads((ROOT / row['construction']).read_text()))
                      for row in entry['candidates']]
        first = json.loads(candidates[0]['config.json'])
        self.assertEqual(first['site']['other_approach'][1], -12)
        self.assertEqual(first['site']['other_entry'], original['site']['other_entry'])
        self.assertEqual(first['site']['routes']['other'][-1], original['site']['routes']['other'][-1])
        self.assertNotEqual(candidates[1]['runner.py'], primary['runner.py'])
        self.assertIn('lookahead_m=(4.0 if role == "other" else 5.0)', candidates[1]['runner.py'])
        third = json.loads(candidates[2]['config.json'])
        self.assertEqual(third['site']['cameras']['overview'][2], 28)
        self.assertEqual(third['site']['cameras']['approach'][0], -18)
        self.assertEqual(third['cameras'], original['cameras'])


if __name__ == '__main__':
    unittest.main()
