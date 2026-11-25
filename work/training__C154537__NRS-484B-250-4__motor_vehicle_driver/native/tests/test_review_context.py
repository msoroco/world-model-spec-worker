import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / 'review_context.py'
SPEC = importlib.util.spec_from_file_location('review_context', MODULE)
review_context = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review_context)


class ReviewContext(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in review_context.SOURCE_FILES:
            (self.root / name).write_text('{"source_kind":"original_native"}' if name == 'scene-survey.json' else 'original source\n')
        self.review = {
            'format': 'c154537-source-context-review-v1',
            'reviewer': 'test reviewer', 'review_method': 'source and image inspection',
            'original_sha256': {name: review_context.sha(self.root / name)
                                for name in review_context.SOURCE_FILES},
            'topics': {name: {'status': 'unresolved', 'source_refs': ['scene-survey.json'],
                              'observation': 'source inspected', 'reason': 'physical context unknown'}
                       for name in review_context.TOPICS},
        }

    def test_source_bound_review_preserves_uncertainty(self):
        result = review_context.validate(self.root, self.review)
        self.assertEqual(result['confirmed_topics'], [])
        self.assertEqual(len(result['unresolved_topics']), 6)
        self.assertFalse(result['physical_acceptance_claimed'])

    def test_mutated_original_is_rejected(self):
        (self.root / 'overview.mkv').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'hash differs: overview'):
            review_context.validate(self.root, self.review)

    def test_missing_topic_source_is_rejected(self):
        self.review['topics']['through_highway']['source_refs'] = []
        with self.assertRaisesRegex(ValueError, 'reference missing'):
            review_context.validate(self.root, self.review)

    def test_synthetic_source_is_rejected(self):
        (self.root / 'scene-survey.json').write_text(json.dumps({'source_kind': 'synthetic_original_shape'}))
        self.review['original_sha256']['scene-survey.json'] = review_context.sha(self.root / 'scene-survey.json')
        with self.assertRaisesRegex(ValueError, 'original Native'):
            review_context.validate(self.root, self.review)


if __name__ == '__main__':
    unittest.main()
