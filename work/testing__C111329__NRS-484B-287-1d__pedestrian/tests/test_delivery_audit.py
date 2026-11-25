import copy
import json
import unittest

from test_saved_process import SavedProcessTests
from delivery_audit import audit


class DeliveryAuditTests(SavedProcessTests):
    def test_independent_positive_and_negative(self):
        self.run_process()
        saved_ref = self.write('saved-ref.json', json.loads((self.root / 'receipt.json').read_text()))
        checked = audit(self.root, self.packet['case_id'], self.site_ref,
                        self.native_ref, self.camera_ref, saved_ref,
                        expected_frames=3, allow_diagnostic=True)
        self.assertEqual(checked['decoded_png_count'], 12)
        self.assertIsNone(checked['legal_verdict'])
        with self.assertRaisesRegex(ValueError, 'diagnostic Native'):
            audit(self.root, self.packet['case_id'], self.site_ref,
                  self.native_ref, self.camera_ref, saved_ref, expected_frames=3)
        changed = copy.deepcopy(json.loads((self.root / 'receipt.json').read_text()))
        changed['measurement']['camera_frames_verified'] = False
        bad_ref = self.write('bad-saved.json', changed)
        with self.assertRaisesRegex(ValueError, 'measurement or full-pixel'):
            audit(self.root, self.packet['case_id'], self.site_ref,
                  self.native_ref, self.camera_ref, bad_ref,
                  expected_frames=3, allow_diagnostic=True)
        (self.root / self.manifest['sources'][4]['path']).write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            audit(self.root, self.packet['case_id'], self.site_ref,
                  self.native_ref, self.camera_ref, saved_ref,
                  expected_frames=3, allow_diagnostic=True)


if __name__ == '__main__':
    unittest.main()
