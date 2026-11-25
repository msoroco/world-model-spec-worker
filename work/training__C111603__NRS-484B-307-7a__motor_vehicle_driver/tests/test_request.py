import copy
import unittest
from request import CASES, FRAMES, check, rows, validate_request


class ArrowRequestProof(unittest.TestCase):
    def test_controlled_pair(self):
        values = {case: check(case) for case in CASES}
        self.assertEqual({r['frames'] for r in values.values()}, {FRAMES})
        self.assertFalse(values['yield_then_turn']['other_requested_inside_at_entry'])
        self.assertTrue(values['turn_during_other_passage']['other_requested_inside_at_entry'])
        a, b = rows('yield_then_turn'), rows('turn_during_other_passage')
        for row_a, row_b in zip(a, b):
            self.assertEqual(row_a['requested_other_xy_m'], row_b['requested_other_xy_m'])
            self.assertEqual(row_a['requested_arrow'], row_b['requested_arrow'])

    def test_unknown_case_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            rows('unknown')

    def test_changed_request_rejected(self):
        original = rows('turn_during_other_passage')
        for index, key, value, error in (
            (200, 'requested_arrow', {'direction': 'left'}, 'arrow'),
            (200, 'requested_other_xy_m', [20, 20], 'other_xy'),
            (205, 'other_traffic_lawful_status', 'lawful', 'unreviewed'),
            (205, 'original_native_observed', True, 'unreviewed')):
            changed = copy.deepcopy(original)
            changed[index][key] = value
            with self.assertRaisesRegex(ValueError, error):
                validate_request(changed, 'turn_during_other_passage')
        with self.assertRaisesRegex(ValueError, 'frame inventory'):
            validate_request(original[:-1], 'turn_during_other_passage')


if __name__ == '__main__':
    unittest.main()
