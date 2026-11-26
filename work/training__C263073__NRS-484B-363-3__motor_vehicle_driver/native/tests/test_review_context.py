import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from review_context import EXCEPTIONS, EXCEPTION_TOPICS, REQUIRED, attach_original_review, verified_sources


class IndependentSchoolSourceTests(unittest.TestCase):
    def make_review(self, root):
        records = {}
        for topic in REQUIRED:
            path = root / (topic + '.json')
            path.write_text(json.dumps({'topic': topic, 'synthetic_fixture': True}) + '\n')
            records[topic] = {'topic': topic, 'path': path.name,
                              'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                              'reviewer': 'synthetic-test', 'observation': 'synthetic source-shape fixture'}
        dispositions = {name: {'status': 'unresolved', 'source_topics': sorted(EXCEPTION_TOPICS[name]),
                               'reason': 'Synthetic fixture does not resolve legal applicability'}
                        for name in EXCEPTIONS}
        return {'independent_review': {'format': 'c263073-source-review-v1',
                                       'records': records, 'exception_dispositions': dispositions}}

    def test_binds_all_five_exception_sources(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            review = self.make_review(root)
            result = verified_sources(root, review)
            self.assertEqual(set(result['records']), set(REQUIRED))
            self.assertEqual(set(result['exception_dispositions']), set(EXCEPTIONS))

    def test_changed_original_packet_rejected(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            review = self.make_review(root)
            (root / 'school_session.json').write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'hash differs: school_session'):
                verified_sources(root, review)

    def test_exception_cannot_bind_unrelated_topics(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            review = self.make_review(root)
            review['independent_review']['exception_dispositions']['d_operational_beacon_class_hours']['source_topics'] = ['zone_sign']
            with self.assertRaisesRegex(ValueError, 'topics incomplete: d_operational_beacon_class_hours'):
                verified_sources(root, review)

    def test_escape_outside_attempt_rejected(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            review = self.make_review(root)
            review['independent_review']['records']['zone_sign']['path'] = '../zone_sign.json'
            with self.assertRaisesRegex(ValueError, 'file missing: zone_sign'):
                verified_sources(root, review)

    def test_seals_review_sources_before_saved_processing(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            source = root / 'independent'
            source.mkdir()
            review = self.make_review(source)
            (source / 'review.json').write_text(json.dumps(review) + '\n')
            attempt = root / 'original-attempt'
            sealed = attach_original_review(attempt, source)
            self.assertEqual(set(verified_sources(attempt, {'independent_review': sealed})['records']), set(REQUIRED))
            self.assertTrue(all(item['path'].startswith('review-sources/') for item in sealed['records'].values()))
