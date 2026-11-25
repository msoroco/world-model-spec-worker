import importlib.util
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location('compare_saved_c109171', HERE / 'compare_saved.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FixedDeviceTest(unittest.TestCase):
    def test_same_source_passes(self):
        module.require_fixed_device({'pedestrian_device_source_sha256': 'a' * 64},
                                    {'pedestrian_device_source_sha256': 'a' * 64})

    def test_changed_source_fails(self):
        with self.assertRaisesRegex(ValueError, 'pedestrian_device_source_sha256'):
            module.require_fixed_device({'pedestrian_device_source_sha256': 'a' * 64},
                                        {'pedestrian_device_source_sha256': 'b' * 64})

    def test_missing_source_fails(self):
        with self.assertRaisesRegex(ValueError, 'pedestrian_device_source_sha256'):
            module.require_fixed_device({}, {'pedestrian_device_source_sha256': 'a' * 64})

    def test_production_review_must_be_fixed(self):
        with self.assertRaisesRegex(ValueError, 'permission_review_sha256'):
            module.require_fixed_review(
                {'diagnostic_fixture': False, 'permission_review_sha256': 'a' * 64},
                {'diagnostic_fixture': False, 'permission_review_sha256': 'b' * 64})

    def test_production_review_must_be_present(self):
        with self.assertRaisesRegex(ValueError, 'permission_review_sha256'):
            module.require_fixed_review({'diagnostic_fixture': False},
                                        {'diagnostic_fixture': False})

    def test_mixed_source_kinds_rejected(self):
        with self.assertRaisesRegex(ValueError, 'mixes diagnostic'):
            module.require_fixed_review({'diagnostic_fixture': True},
                                        {'diagnostic_fixture': False})

    def test_diagnostic_pair_has_no_review_claim(self):
        module.require_fixed_review({'diagnostic_fixture': True},
                                    {'diagnostic_fixture': True})


if __name__ == '__main__':
    unittest.main()
