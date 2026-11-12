import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
spec = importlib.util.spec_from_file_location('fallback_audit', ROOT / 'prove_fallback_isolation.py')
fallback_audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fallback_audit)
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.candidate_constructions import validate


class AllFallbacksTest(unittest.TestCase):
    def test_all_three_each_pass_pinned_candidate_validation(self):
        manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
        for entry in manifest['cases']:
            with self.subTest(case=entry['case_id']):
                result = validate(ROOT, entry, 'NRS-484B-250-2', 'C125714',
                                  required=True, require_alternate=True, candidate_count=4)
                self.assertEqual(result['fallbacks'], ['fallback1', 'fallback2', 'fallback3'])
        self.assertEqual(len(fallback_audit.audit()['checked']), 24)


if __name__ == '__main__':
    unittest.main()
