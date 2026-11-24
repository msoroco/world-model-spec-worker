import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from comparison_audit import REVIEWED_KEYS, original_condition_record
from intersection_observables import SourceError


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, value):
    path.write_text(json.dumps(value, sort_keys=True)+'\n')


class OriginalConditionTests(unittest.TestCase):
    def test_review_must_bind_exact_sealed_original_sources(self):
        case = 'exact-case'
        with tempfile.TemporaryDirectory() as tmp:
            attempt = Path(tmp)
            put(attempt/'reviewed-route.json', {'case_id': case,
                'vehicle_blueprint': 'vehicle.reviewed', 'approach_lane': 'lane-1'})
            put(attempt/'source-manifest.json', {'case_id': case})
            (attempt/'trace.jsonl').write_text('original trace\n')
            put(attempt/'capture-seal.json', {
                'sources': {'trace.jsonl': sha(attempt/'trace.jsonl')}})
            review = {'case_id': case, 'independent_review': True,
                      'reviewer': 'independent-reviewer', 'review_note': 'all original frames',
                      'source_sha256': {name: sha(attempt/name) for name in
                          ('capture-seal.json', 'source-manifest.json', 'reviewed-route.json')},
                      'conditions': {key: 'none' for key in REVIEWED_KEYS},
                      'field_sources': {key: {'path': 'trace.jsonl',
                                             'sha256': sha(attempt/'trace.jsonl')}
                                        for key in REVIEWED_KEYS}}
            put(attempt/'condition-review.json', review)
            observed = {'map_id': 'map-1', 'source_seals': {
                'boundary': 'boundary-hash', 'trace': 'trace-hash', 'activity': 'activity-hash'},
                'source_refs': ['original'],
                'frames': [{'within_or_touching_boundary': True}] * 900}
            delivery = {'canonical_delivery_acceptance': 'source_verified',
                        'videos': {name: {} for name in
                                   ('overview', 'approach', 'reference_corner', 'driver_reference')}}
            with patch('delivery_audit.audit', return_value=delivery), \
                 patch('finalize_observables.finalize', return_value=observed):
                result = original_condition_record(attempt, case)
                self.assertEqual(result['condition_receipt']['destination'], 'inside')
                self.assertEqual(result['condition_receipt']['activity'], 'none')
                review['field_sources']['activity']['sha256'] = '0' * 64
                put(attempt/'condition-review.json', review)
                with self.assertRaisesRegex(SourceError, 'condition source missing: activity'):
                    original_condition_record(attempt, case)


if __name__ == '__main__':
    unittest.main()
