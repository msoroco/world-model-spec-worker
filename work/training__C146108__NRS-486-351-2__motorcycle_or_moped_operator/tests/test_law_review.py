"""Subsection 2/3 alternatives and missing-source rejection."""
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'native'))
from law_review import review


class LawReview(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch, prefix='c146108-law-')
        self.root = Path(self.temp.name)
        source = self.root / 'participant-source.json'
        source.write_text('{"source":"synthetic identity test"}\n')
        self.context = {'rider_class': 'motorcycle', 'other_class': 'motor_vehicle',
                        'observed_action': 'pass', 'abreast_count': 2,
                        'driver_consent': None,
                        'classification_source': {'path': source.name,
                            'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}}

    def tearDown(self):
        self.temp.cleanup()

    def test_car_pass_never_qualifies_for_two_rider_exception(self):
        result = review(self.context, self.root)
        self.assertTrue(result['same_lane_prohibition_action_observed'])
        self.assertFalse(result['subsection_3_pair_eligible'])
        self.assertFalse(result['legal_verdict_claimed'])

    def test_following_is_not_an_action(self):
        self.context['observed_action'] = 'following'
        self.assertFalse(review(self.context, self.root)['same_lane_prohibition_action_observed'])

    def test_two_motorcycles_need_source_verified_consent(self):
        self.context.update(other_class='motorcycle', observed_action='abreast')
        self.assertTrue(review(self.context, self.root)['consent_unverified'])
        self.context['driver_consent'] = True
        with self.assertRaisesRegex(ValueError, 'consent cannot be inferred'):
            review(self.context, self.root)
        source = self.root / 'consent-source.json'
        source.write_text('{"source":"synthetic consent test"}\n')
        self.context['consent_source'] = {'path': source.name,
            'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        self.assertTrue(review(self.context, self.root)['subsection_3_exception_established'])

    def test_trimobile_has_no_subsection_three_exception(self):
        self.context.update(rider_class='trimobile', other_class='motorcycle',
                            observed_action='abreast')
        self.assertFalse(review(self.context, self.root)['subsection_3_pair_eligible'])

    def test_changed_identity_source_rejected(self):
        (self.root / 'participant-source.json').write_text('{}\n')
        with self.assertRaisesRegex(ValueError, 'source missing or changed'):
            review(self.context, self.root)


if __name__ == '__main__':
    unittest.main()
