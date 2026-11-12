"""Decoded controlled-pair CPU path; all receipts stay ineligible for acceptance."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import test_delivery_positive_shape as delivery_shape
from comparison_audit import audit_pair
from delivery_audit import audit_complete


class PositiveComparisonShapeTest(unittest.TestCase):
    def test_full_pair_and_stale_decode_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit_paths = []
            for suffix, overlap, station in (('reference', 0.0, -12.0),
                                             ('contrast', 5.2, 0.0)):
                case_id = HERE.name + '__' + suffix
                place = root / suffix
                place.mkdir()
                attempt, owner, saved, construction, pixel, access, primary, core = (
                    delivery_shape.PositiveDeliveryShapeTest().make_shape(
                        place, case_id=case_id, overlap=overlap, stop_x=station))
                receipt = audit_complete(attempt, saved, owner, case_id,
                    construction, pixel, access, primary, core, place / 'decode',
                    'unit-job-' + suffix, 1, 'unit-recording-' + suffix,
                    test_shape=True)
                self.assertFalse(receipt['passed'])
                path = place / 'delivery-audit.json'
                path.write_text(json.dumps(receipt))
                audit_paths.append(path)
            result = audit_pair(*audit_paths, test_shape=True)
            self.assertFalse(result['passed'])
            self.assertTrue(result['source_shaped_unit_test'])
            self.assertEqual(result['measured_overlap_m'], [0.0, 5.2])
            with self.assertRaisesRegex(ValueError, 'independent original delivery'):
                audit_pair(*audit_paths)
            altered = json.loads(audit_paths[1].read_text())
            altered['source_decode_receipt_sha256'] = '0' * 64
            audit_paths[1].write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError, 'primary decode receipt changed'):
                audit_pair(*audit_paths, test_shape=True)


if __name__ == '__main__':
    unittest.main()
