"""Independent municipal source join and rejection tests."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from source_review import ASSIGNMENT, join


class MunicipalReviewTests(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / '.runtime-work' / 'c150129'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.attempt = Path(self.temporary.name)
        (self.attempt / 'source_context').mkdir()
        self.inventory = {
            'assignment_id': ASSIGNMENT, 'space_id': 'city-space-01',
            'space_polygon_xy_m': [[0, 0], [4, 0], [4, 3], [0, 3]],
            'city_street_source_id': None, 'council_designation_source_id': None,
            'posting_or_marking_source_id': None, 'subject_status_source_id': None,
            'subject_city_vehicle': None,
        }
        inventory_file = self.attempt / 'parking-inventory.json'
        inventory_file.write_text(json.dumps(self.inventory) + '\n')
        self.review = {
            'format': 'c150129-independent-source-review-v1',
            'assignment_id': ASSIGNMENT,
            'case_id': ASSIGNMENT + '__controlled_2',
            'native_inventory_sha256': hashlib.sha256(inventory_file.read_bytes()).hexdigest(),
        }
        fields = {
            'city_street': {'is_city_street': True},
            'council_designation': {'designated_for_city_vehicles': True,
                                    'space_id': 'city-space-01'},
            'posting_or_marking': {'posted_or_marked': True, 'space_id': 'city-space-01'},
            'subject_vehicle_status': {'subject_city_vehicle': False},
        }
        for field, values in fields.items():
            name = 'source_context/' + field + '.txt'
            source = self.attempt / name
            source.write_text('Synthetic source for CPU provenance test: ' + field + '\n')
            self.review[field] = dict(values, path=name,
                sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                source_id='synthetic-' + field,
                review_method='CPU synthetic provenance join test')
        (self.attempt / 'review.json').write_text(json.dumps(self.review) + '\n')

    def test_positive_join_preserves_native_inventory(self):
        result = join(self.attempt, self.inventory, self.review)
        self.assertFalse(result['subject_city_vehicle'])
        self.assertEqual(result['posting_space_id'], 'city-space-01')
        self.assertIsNone(self.inventory['subject_city_vehicle'])
        self.assertIn('legal sufficiency unreviewed', result['source_review_status'])

    def test_rejects_unbound_and_stale_evidence(self):
        for field, key, value, error in (
            ('city_street', 'is_city_street', None, 'City-street jurisdiction unconfirmed'),
            ('council_designation', 'space_id', 'other', 'City Council designated-space association unconfirmed'),
            ('posting_or_marking', 'space_id', 'other', 'Posted-space association unconfirmed'),
            ('subject_vehicle_status', 'subject_city_vehicle', None, 'Non-City subject vehicle status unconfirmed'),
            ('posting_or_marking', 'sha256', '0' * 64, 'Independent source hash differs: posting_or_marking'),
        ):
            with self.subTest(field=field, key=key):
                prior = self.review[field][key]
                self.review[field][key] = value
                with self.assertRaisesRegex(ValueError, error):
                    join(self.attempt, self.inventory, self.review)
                self.review[field][key] = prior

    def test_rejects_wrong_native_binding(self):
        self.review['native_inventory_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'another Native inventory'):
            join(self.attempt, self.inventory, self.review)


if __name__ == '__main__':
    unittest.main()
