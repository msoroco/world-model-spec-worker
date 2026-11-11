import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime' / 'scenario_pipeline'))
from worker_exchange.candidate_constructions import validate


class FallbackConstructionTests(unittest.TestCase):
    def test_four_exact_cases_have_source_bound_distinct_remedies(self):
        for name in ('delivery-construction-manifest.json',
                     'variant-construction-manifest.json'):
            manifest = json.loads((HERE / name).read_text())
            for entry in manifest['cases']:
                with self.subTest(case=entry['case_id']):
                    outcome = validate(HERE, entry, 'NRS-484B-207-1', 'C110161',
                                       required=True, require_alternate=True,
                                       candidate_count=4)
                    self.assertEqual(outcome['fallbacks'],
                                     ['fallback1', 'fallback2', 'fallback3'])
                    self.assertEqual(len({c['trigger']['metric'] for c in entry['candidates']}), 3)
                    self.assertEqual(len({c['changed_knobs'][0] for c in entry['candidates']}), 3)
                    for candidate in entry['candidates']:
                        suffix = entry['case_id'].rsplit('__', 1)[-1]
                        proof = HERE / ('delivery-' + suffix + '-' + candidate['id'] + '-saved-proof.json')
                        saved = json.loads(proof.read_text())
                        self.assertEqual(saved['construction_sha256'],
                                         candidate['construction_sha256'])
                        self.assertEqual(saved['candidate_id'], candidate['id'])


if __name__ == '__main__':
    unittest.main()
