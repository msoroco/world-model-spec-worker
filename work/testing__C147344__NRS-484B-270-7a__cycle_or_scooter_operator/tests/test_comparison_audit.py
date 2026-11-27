"""Positive and negative source-bound comparison audits."""

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_audit import ASSIGNMENT, PAIRS, audit
from interference import CASES, measure_original
from test_interference import rows_for, scene_for


def report(slug):
    case = next(item for item in CASES if item.suffix == slug)
    scene = scene_for(case)
    return {'case_id': ASSIGNMENT + '__' + slug,
            'observation': measure_original(rows_for(scene, case), scene,
                                            case),
            'original_sources_sha256': 'c' * 64,
            'physical_acceptance_claimed': False,
            'legal_judgment': None}


class ComparisonAuditTest(unittest.TestCase):
    def test_all_exact_pairs_pass(self):
        for name, slugs in PAIRS.items():
            with self.subTest(comparison=name):
                result = audit(name, report(slugs[0]), report(slugs[1]))
                self.assertTrue(result['fixed_conditions_checked'])
                self.assertTrue(result['deliberate_difference_checked'])
                self.assertIsNone(result['legal_judgment'])

    def test_missing_original_source_rejected(self):
        left, right = report(PAIRS['intent_source'][0]), report(
            PAIRS['intent_source'][1])
        right.pop('original_sources_sha256')
        with self.assertRaisesRegex(ValueError, 'source seal'):
            audit('intent_source', left, right)

    def test_changed_fixed_road_rejected(self):
        left, right = report(PAIRS['merge_effect'][0]), report(
            PAIRS['merge_effect'][1])
        right['observation']['reviewed_road_source_sha256'] = 'd' * 64
        with self.assertRaisesRegex(ValueError, 'fixed original source'):
            audit('merge_effect', left, right)

    def test_false_intent_contrast_rejected(self):
        left, right = report(PAIRS['intent_source'][0]), report(
            PAIRS['intent_source'][1])
        right['observation']['declared_intention'] = copy.deepcopy(
            left['observation']['declared_intention'])
        with self.assertRaisesRegex(ValueError, 'authored-intent contrast'):
            audit('intent_source', left, right)

    def test_false_merge_contrast_rejected(self):
        left, right = report(PAIRS['merge_presence'][0]), report(
            PAIRS['merge_presence'][1])
        right['observation']['requested_bicycle_path'] = 'merge'
        with self.assertRaisesRegex(ValueError, 'merge-presence contrast'):
            audit('merge_presence', left, right)


if __name__ == '__main__':
    unittest.main()
