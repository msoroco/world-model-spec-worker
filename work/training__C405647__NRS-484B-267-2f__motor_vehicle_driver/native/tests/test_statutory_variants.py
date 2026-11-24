"""Distinguish supplied statutory alternatives without inventing 484B.607 duties."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from statutory_variants import SourceState, branch_label


BASE = dict(subject_is_other_driver=True, source_vehicle_kind='authorized_emergency',
            authority_reviewed=True, qualifying_flash_reviewed=True,
            subject_approaching_source=True, source_moving=True,
            visible_movement=False, visible_driver_hand_signal=False,
            source_approaching_subject=True, source_stopped=False,
            officer_directed_otherwise=False)


class StatutoryVariants(unittest.TestCase):
    def state(self, **overrides):
        return SourceState(**(BASE | overrides))

    def test_approaches_with_official_vehicle(self):
        self.assertEqual(branch_label(self.state(source_vehicle_kind='regulatory_agency_official')),
                         'approaches_referral_subsection_1')

    def test_visible_preparation_by_movement_or_hand_signal(self):
        for field in ('visible_movement', 'visible_driver_hand_signal'):
            with self.subTest(field=field):
                self.assertEqual(branch_label(self.state(source_moving=False, **{field: True})),
                                 'approaches_referral_subsection_1')
        self.assertEqual(branch_label(self.state(source_moving=False)),
                         'movement_or_visible_preparation_unproved')

    def test_stopped_referral_has_no_inferred_duty(self):
        self.assertEqual(branch_label(self.state(source_approaching_subject=False, source_stopped=True)),
                         'stops_referral_484B_607')

    def test_officer_direction_exception(self):
        self.assertEqual(branch_label(self.state(officer_directed_otherwise=True)),
                         'officer_direction_exception')

    def test_missing_authority_or_lamps_requires_review(self):
        for field in ('authority_reviewed', 'qualifying_flash_reviewed'):
            with self.subTest(field=field):
                self.assertEqual(branch_label(self.state(**{field: False})),
                                 'source_review_pending')

    def test_conflicting_trajectory_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'cannot hold together'):
            branch_label(self.state(source_stopped=True))


if __name__ == '__main__':
    unittest.main()
