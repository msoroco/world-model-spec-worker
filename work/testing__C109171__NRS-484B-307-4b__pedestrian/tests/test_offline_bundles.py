import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_offline_draft import SOURCES
from saved_measurement import ASSIGNMENT, EXPECTED


class OfflineBundleTests(unittest.TestCase):
    def test_four_exact_cases_and_embedded_source_bindings(self):
        manifest = json.loads((ROOT / 'execution-manifest.draft.json').read_text())
        self.assertEqual(manifest['status'], 'diagnostic_original_sources_pending')
        self.assertEqual({row['case_id'] for row in manifest['cases']},
                         {ASSIGNMENT + '__' + suffix for suffix in EXPECTED})
        for row in manifest['cases']:
            path = ROOT / row['construction']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                             row['construction_sha256'])
            construction = json.loads(path.read_text())
            self.assertTrue(construction['diagnostic_only'])
            files = {item['path']: item['content'] for item in construction['files']}
            for name in SOURCES:
                self.assertEqual(files[name], (ROOT / name).read_text())
            config = json.loads(files['config.json'])
            suffix = row['case_id'].removeprefix(ASSIGNMENT + '__')
            self.assertEqual(config['expected_observations'], list(EXPECTED[suffix]))
            self.assertEqual(config['selected_case_id'], row['case_id'])
            self.assertEqual(config['plan_sha256'], hashlib.sha256(
                (ROOT / 'case-plan.json').read_bytes()).hexdigest())
            self.assertEqual(config['frame_count'], 600)
            self.assertEqual(config['fps'], 20)
            self.assertEqual(set(config['cameras']), {'front', 'left', 'right', 'rear'})


if __name__ == '__main__':
    unittest.main()
