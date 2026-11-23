import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('comparison_audit', Path(__file__).resolve().parents[1] / 'comparison_audit.py')
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


def record():
    return {'map_id': 'town', 'actor_id': 'ego', 'capture_profile': '4cam-20hz', 'duration_frames': 900,
            'approach_device_id': 'A', 'destination_device_id': 'B', 'parcel_class': 'private',
            'route_class': 'property', 'approach_state': 'red_alone', 'destination_state': 'yellow',
            'purpose': 'avoid_red', 'trace_sha256': 'a'*64, 'map_source_sha256': 'b'*64, 'frame_map_sha256': 'c'*64}


class ComparisonAuditTests(unittest.TestCase):
    def test_one_declared_difference_passes(self):
        a, b = record(), record()
        b['parcel_class'] = 'public'
        self.assertTrue(audit_module.audit(a, b, 'parcel_class')['source_seals_checked'])

    def test_extra_difference_rejected(self):
        a, b = record(), record()
        b['parcel_class'] = 'public'
        b['purpose'] = 'other'
        with self.assertRaisesRegex(ValueError, 'undeclared difference'):
            audit_module.audit(a, b, 'parcel_class')

    def test_missing_deliberate_difference_rejected(self):
        with self.assertRaisesRegex(ValueError, 'deliberate difference'):
            audit_module.audit(record(), record(), 'parcel_class')

    def test_missing_trace_seal_rejected(self):
        a, b = record(), record()
        b['parcel_class'] = 'public'
        del b['trace_sha256']
        with self.assertRaisesRegex(ValueError, 'seals required'):
            audit_module.audit(a, b, 'parcel_class')

    def test_different_original_source_rejected(self):
        a, b = record(), record()
        b['parcel_class'] = 'public'
        b['map_source_sha256'] = 'd'*64
        with self.assertRaisesRegex(ValueError, 'original map/property source'):
            audit_module.audit(a, b, 'parcel_class')


if __name__ == '__main__':
    unittest.main()
