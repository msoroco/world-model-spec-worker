import importlib.util
import json
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
fixture_spec = importlib.util.spec_from_file_location('test_saved_delivery', BASE / 'tests/test_saved_delivery.py')
fixture_module = importlib.util.module_from_spec(fixture_spec)
sys.modules[fixture_spec.name] = fixture_module
fixture_spec.loader.exec_module(fixture_module)
audit_spec = importlib.util.spec_from_file_location('comparison_audit', BASE / 'comparison_audit.py')
audit_module = importlib.util.module_from_spec(audit_spec)
sys.modules[audit_spec.name] = audit_module
audit_spec.loader.exec_module(audit_module)
spec = importlib.util.spec_from_file_location('comparison_delivery', BASE / 'comparison_delivery.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class OriginalComparisonTests(unittest.TestCase):
    def setUp(self):
        self.left = fixture_module.SavedDeliveryTests()
        self.left.setUp()
        self.addCleanup(self.left.doCleanups)
        self.right = fixture_module.SavedDeliveryTests()
        self.right.setUp()
        self.addCleanup(self.right.doCleanups)
        case = self.right.case.replace('private_bypass', 'public_bypass')
        trace = json.loads((self.right.root / 'trace.json').read_text())
        trace['case_id'] = case
        self.right.bundle['case_id'] = case
        self.right.bundle['case'] = self.right.write('case.json', json.dumps({'case_id': case}) + '\n')
        self.right.bundle['trace'] = self.right.write('trace.json', json.dumps(trace) + '\n')
        packet = json.loads((self.right.root / 'map.json').read_text())
        authority = json.loads((self.right.root / 'original-map.json').read_text())
        packet['properties'][0]['status'] = 'public'
        authority['properties'][0]['status'] = 'public'
        (self.right.root / 'original-map.json').write_text(json.dumps(authority) + '\n')
        packet['source']['sha256'] = fixture_module.audit.sha((self.right.root / 'original-map.json').read_bytes())
        self.right.bundle['map'] = self.right.write('map.json', json.dumps(packet) + '\n')

    def test_original_pair_decodes_and_checks_fixed_conditions(self):
        result = module.audit_pair('public_vs_private_property', self.left.root, self.left.bundle,
                                   self.right.root, self.right.bundle, expected_frames=20)
        self.assertTrue(result['source_seals_checked'])
        self.assertEqual(result['right']['parcel_class'], 'public')
        self.assertFalse(result['physical_acceptance_claimed'])

    def test_changed_fixed_signal_identity_rejected(self):
        trace = json.loads((self.right.root / 'trace.json').read_text())
        for item in trace['approach_signal_history']:
            item['device_id'] = 'different-device'
        trace['approach_signal']['device_id'] = 'different-device'
        self.right.bundle['trace'] = self.right.write('trace.json', json.dumps(trace) + '\n')
        with self.assertRaisesRegex(ValueError, 'fixed condition differs or absent: approach_device_id'):
            module.audit_pair('public_vs_private_property', self.left.root, self.left.bundle,
                              self.right.root, self.right.bundle, expected_frames=20)


if __name__ == '__main__':
    unittest.main()
