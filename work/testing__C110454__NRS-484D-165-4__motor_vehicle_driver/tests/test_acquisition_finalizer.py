import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from acquisition_finalizer import finalize_acquisition
import test_delivery_audit


class FinalizerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_delivery_audit.DeliveryAuditTests(
            methodName='test_positive_diagnostic_integrity_and_delivery_rejection')
        self.fixture.setUp()
        self.root = self.fixture.root
        receipt = json.loads((self.root / 'native-receipt.json').read_text())
        receipt['original_camera_media'] = self.fixture.manifest['media']
        (self.root / 'native-source-receipt.json').write_text(json.dumps(receipt))
        (self.root / 'acquisition.json').unlink()

    def tearDown(self):
        self.fixture.doCleanups()

    def test_sealed_sources_build_and_audit_diagnostic_manifest(self):
        result = finalize_acquisition(self.root, case_id=self.fixture.case_id,
                                      allow_diagnostic=True)
        manifest = json.loads((self.root / 'acquisition.json').read_text())
        self.assertEqual(manifest['native_receipt']['path'], 'native-source-receipt.json')
        self.assertTrue(result['delivery_audit']['saved_source_integrity_passed'])
        self.assertFalse(result['physical_acceptance_claimed'])
        with self.assertRaisesRegex(ValueError, 'already exists'):
            finalize_acquisition(self.root, case_id=self.fixture.case_id,
                                 allow_diagnostic=True)

    def test_wrong_media_and_diagnostic_as_native_rejected_without_manifest(self):
        with self.assertRaisesRegex(ValueError, 'provenance mismatch'):
            finalize_acquisition(self.root, case_id=self.fixture.case_id)
        self.assertFalse((self.root / 'acquisition.json').exists())
        (self.root / 'overview.txt').write_text('changed source')
        with self.assertRaisesRegex(ValueError, 'media hash mismatch'):
            finalize_acquisition(self.root, case_id=self.fixture.case_id,
                                 allow_diagnostic=True)
        self.assertFalse((self.root / 'acquisition.json').exists())

    def test_invalid_attempt_rolls_back_manifest_after_saved_audit(self):
        rows = (self.root / 'actor-state.jsonl').read_text().splitlines()
        rows[0] = json.dumps(dict(json.loads(rows[0]), parking_brake=False))
        actor = self.root / 'actor-state.jsonl'
        actor.write_text('\n'.join(rows) + '\n')
        receipt_file = self.root / 'native-source-receipt.json'
        receipt = json.loads(receipt_file.read_text())
        import hashlib
        receipt['source_hashes']['actor-state.jsonl'] = hashlib.sha256(actor.read_bytes()).hexdigest()
        receipt_file.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, 'parked'):
            finalize_acquisition(self.root, case_id=self.fixture.case_id,
                                 allow_diagnostic=True)
        self.assertFalse((self.root / 'acquisition.json').exists())


if __name__ == '__main__':
    unittest.main()
