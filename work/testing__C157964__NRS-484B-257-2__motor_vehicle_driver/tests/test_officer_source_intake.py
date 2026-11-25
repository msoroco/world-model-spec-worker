import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('c157964_sub2_source_intake',
                                              ROOT / 'officer_source_intake.py')
INTAKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INTAKE)


class OfficerSourceIntakeTests(unittest.TestCase):
    def fixture(self, root):
        names = ('road', 'sign_inventory', 'officer_authority', 'officer_control',
                 'other_route', 'camera_sight_review')
        bindings = {}
        for name in names:
            path = root / (name + '.txt')
            path.write_text('test fixture ' + name)
            bindings[name] = {'path': path.name,
                              'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        return {'format': 'worker-officer-subsection-2-source-review',
                'site_id': 'test-site', 'sources': bindings,
                'review': {'site_id': 'test-site', 'non_through_highway': True,
                           'ego_entrance_id': 'ego', 'other_entrance_id': 'other',
                           'entrances': [{'entrance_id': 'ego', 'device': 'stop',
                                          'sign_visible': True},
                                         {'entrance_id': 'other', 'device': 'none',
                                          'sign_visible': True}],
                           'officer_authority_reviewed': True,
                           'officer_control_reviewed': True,
                           'original_camera_sight_reviewed': True}}

    def test_structural_intake_keeps_legal_judgment_unresolved(self):
        with tempfile.TemporaryDirectory() as dirname:
            packet = self.fixture(Path(dirname))
            result = INTAKE.validate(dirname, packet)
            self.assertEqual(result['ego_entrance_id'], 'ego')
            self.assertEqual(result['legal_exception_judgment'], 'unresolved')
            self.assertEqual(result['immediate_hazard_judgment'], 'unresolved')

    def test_changed_source_and_missing_review_rejected(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            packet = self.fixture(root)
            (root / 'road.txt').write_text('changed fixture')
            with self.assertRaisesRegex(ValueError, 'Changed source file: road'):
                INTAKE.validate(root, packet)
            packet = self.fixture(root)
            packet['review']['officer_authority_reviewed'] = False
            with self.assertRaisesRegex(ValueError, 'Police authority source review required'):
                INTAKE.validate(root, packet)

    def test_other_entrance_and_unsafe_source_rejected(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            packet = self.fixture(root)
            packet['review']['entrances'][1]['device'] = 'yield'
            with self.assertRaisesRegex(ValueError, 'Non-obligated other entrance'):
                INTAKE.validate(root, packet)
            packet = self.fixture(root)
            packet['sources']['road']['path'] = '../outside.txt'
            with self.assertRaisesRegex(ValueError, 'Unsafe source path'):
                INTAKE.validate(root, packet)


if __name__ == '__main__':
    unittest.main()
