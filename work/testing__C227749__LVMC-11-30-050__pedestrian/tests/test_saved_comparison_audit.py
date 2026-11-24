import importlib.util
import json
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


BASE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
SPEC = importlib.util.spec_from_file_location('saved_comparison_audit', BASE / 'saved_comparison_audit.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SavedComparisonTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = pathlib.Path(self.temp.name)
        self.root = base / BASE.name
        self.scratch = base / 'scratch'
        self.root.mkdir()
        shutil.copyfile(BASE / 'case-plan.json', self.root / 'case-plan.json')
        shutil.copyfile(BASE / 'saved_comparison_audit.py', self.root / 'saved_comparison_audit.py')
        self.names = ['outside_right_angle', 'outside_neither',
                      'outside_shortest_endpoint', 'outside_endpoint_detour',
                      'inside_crosswalk_oblique']
        for name in self.names:
            case = self.root / 'cases' / name
            attempt = self.scratch / ('compat-v4-' + name)
            version = self.scratch / ('process-' + name) / 'v0001' / 'analysis'
            case.mkdir(parents=True)
            attempt.mkdir(parents=True)
            version.mkdir(parents=True)
            for item in ['scene.json', 'config.json', 'construction.json']:
                shutil.copyfile(BASE / 'cases' / name / item, case / item)
            for item in ['scene.json', 'config.json']:
                shutil.copyfile(case / item, attempt / item)
            (version / 'result.json').write_text(json.dumps({'provenance_kind': 'synthetic_fixture'}) + '\n')

    def compare(self):
        with patch.object(MODULE, 'audit_saved', return_value={
            'status': 'software_diagnostic_complete',
            'processing_sha256': 'a' * 64, 'result_sha256': 'b' * 64}):
            return MODULE.compare(self.root, self.scratch)

    def test_three_declared_differences_are_isolated(self):
        rows = self.compare()['comparisons']
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r['declared_difference_isolated'] for r in rows))
        self.assertTrue(all(not r['physical_acceptance'] for r in rows))

    def test_fixed_capture_change_rejected(self):
        config = self.root / 'cases' / 'outside_neither' / 'config.json'
        changed = json.loads(config.read_text())
        changed['rate_hz'] = 10
        config.write_text(json.dumps(changed) + '\n')
        attempt = self.scratch / 'compat-v4-outside_neither' / 'config.json'
        shutil.copyfile(config, attempt)
        with self.assertRaisesRegex(ValueError, 'fixed capture'):
            self.compare()

    def test_unisolated_crosswalk_difference_rejected(self):
        path = self.root / 'cases' / 'inside_crosswalk_oblique' / 'scene.json'
        changed = json.loads(path.read_text())
        changed['crosswalk_boundaries_xy_m'] = json.loads((self.root / 'cases' / 'outside_neither' / 'scene.json').read_text())['crosswalk_boundaries_xy_m']
        path.write_text(json.dumps(changed) + '\n')
        shutil.copyfile(path, self.scratch / 'compat-v4-inside_crosswalk_oblique' / 'scene.json')
        with self.assertRaisesRegex(ValueError, 'variable not isolated'):
            self.compare()


if __name__ == '__main__':
    unittest.main()
