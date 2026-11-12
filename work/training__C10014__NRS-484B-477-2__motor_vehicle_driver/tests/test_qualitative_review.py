"""Source-shaped tests of reviewer bindings, never a legal finding."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import test_delivery_positive_shape as delivery_shape
from delivery_audit import audit_complete, sha
from qualitative_review import REQUIRED, audit


class QualitativeReviewTests(unittest.TestCase):
    def make_review(self, root):
        case_id = HERE.name + '__contrast'
        attempt, owner, saved, construction, pixel, access, primary, core = (
            delivery_shape.PositiveDeliveryShapeTest().make_shape(
                root, case_id=case_id))
        receipt = audit_complete(attempt, saved, owner, case_id, construction,
            pixel, access, primary, core, root / 'decode', 'unit-job', 1,
            'unit-recording', test_shape=True)
        delivery_path = root / 'delivery-audit.json'
        delivery_path.write_text(json.dumps(receipt))
        property_source = Path(json.loads(access.read_text())['property_source']['path'])
        bindings = {name: sha(attempt / name) for name in
            ('native_samples.jsonl', 'road_geometry.json', 'overview.mkv',
             'reference_corner.mkv')}
        bindings['property_source'] = sha(property_source)
        observations = {name: {'assessment': 'stop' if name == 'vehicle_action'
                    else 'indeterminate', 'basis': 'source-shaped unit only',
                    'method': 'test review', 'source_refs': sorted(needed)}
                    for name, needed in REQUIRED.items()}
        review = {'format': 'c10014-qualitative-source-review',
                  'source_shaped_unit_test': True, 'case_id': case_id,
                  'law_input_sha256': sha(REPO / 'inputs' / HERE.name /
                                          'assignment.json'),
                  'delivery_audit_sha256': sha(delivery_path),
                  'property_access_id': 'unit-access',
                  'reviewer': 'CPU unit test', 'method': 'source-shaped only',
                  'source_sha256': bindings, 'observations': observations}
        review_path = root / 'qualitative-review.json'
        review_path.write_text(json.dumps(review))
        return delivery_path, review_path, review

    def test_incomplete_review_and_original_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            delivery, path, review = self.make_review(Path(directory))
            result = audit(delivery, path, test_shape=True)
            self.assertFalse(result['review_completed'])
            self.assertFalse(result['legal_verdict_claimed'])
            with self.assertRaisesRegex(ValueError, 'independent original delivery'):
                audit(delivery, path)
            review['observations']['access_obstructed']['threshold_m'] = 0.1
            path.write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError, 'independent sources'):
                audit(delivery, path, test_shape=True)
            del review['observations']['access_obstructed']['threshold_m']
            review['source_sha256']['native_samples.jsonl'] = '0' * 64
            path.write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError, 'exact source bindings'):
                audit(delivery, path, test_shape=True)

    def test_standing_or_parking_requires_purpose_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            delivery, path, review = self.make_review(root)
            for action in ('stand', 'park'):
                review['observations']['vehicle_action']['assessment'] = action
                path.write_text(json.dumps(review))
                with self.assertRaisesRegex(ValueError, 'driver-purpose source'):
                    audit(delivery, path, test_shape=True)
            purpose = root / 'purpose-source.txt'
            purpose.write_text('source-shaped unit test only')
            review['driver_intent_record'] = str(purpose)
            review['driver_intent_record_sha256'] = sha(purpose)
            path.write_text(json.dumps(review))
            self.assertFalse(audit(delivery, path, test_shape=True)
                             ['review_completed'])

    def test_fully_observed_source_shape_never_becomes_original_review(self):
        with tempfile.TemporaryDirectory() as directory:
            delivery, path, review = self.make_review(Path(directory))
            for kind in ('driveway', 'entrance'):
                for name, item in review['observations'].items():
                    item['assessment'] = (kind if name == 'access_kind' else
                                          'stop' if name == 'vehicle_action' else
                                          'yes')
                path.write_text(json.dumps(review))
                result = audit(delivery, path, test_shape=True)
                self.assertFalse(result['review_completed'])
                self.assertFalse(result['legal_verdict_claimed'])
                self.assertEqual(result['observations']['access_kind'], kind)
            review['legal_verdict'] = 'prohibited'
            path.write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError, 'exact source bindings'):
                audit(delivery, path, test_shape=True)
            del review['legal_verdict']
            review['threshold_m'] = 0.0
            path.write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError, 'exact source bindings'):
                audit(delivery, path, test_shape=True)


if __name__ == '__main__':
    unittest.main()
