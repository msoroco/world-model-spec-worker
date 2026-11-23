"""Static CPU checks for the exact C228133 draft Native runner."""

import copy
import json
from pathlib import Path
import unittest

from runner import check, FRAMES, RATE_HZ
from signal_display import segments


HERE = Path(__file__).resolve().parent
if not (HERE / 'config.json').is_file():
    HERE = HERE.parent


class Offline(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((HERE / 'config.json').read_text())

    def test_full_reference_capture_contract(self):
        result = check(self.config)
        self.assertEqual((result['frames'], RATE_HZ), (600, 20))
        self.assertEqual(FRAMES, 600)
        self.assertEqual(len(result['camera_views']), 4)
        self.assertFalse(result['turn_arrow_pixels_verified'])
        self.assertEqual(result['staged_display_segments'], 35)

    def test_red_disc_and_right_turn_arrow_geometry(self):
        lines = segments()
        self.assertEqual([line[0] for line in lines].count('red'), 32)
        self.assertEqual([line[0] for line in lines].count('green'), 3)
        shaft = lines[32]
        self.assertGreater(shaft[2][0], shaft[1][0])
        self.assertEqual(lines[33][1], shaft[2])
        self.assertEqual(lines[34][1], shaft[2])

    def test_contrast_changes_only_requested_entry(self):
        other = copy.deepcopy(self.config)
        old = self.config['case_suffix']
        new = 'contrast' if old == 'reference' else 'reference'
        other['case_suffix'] = new
        other['pedestrian_enters_highway_requested'] = new == 'contrast'
        other['case_id'] = other['case_id'].replace('__' + old, '__' + new)
        other['selected_case_id'] = other['case_id']
        other['case']['case_id'] = other['case_id']
        self.assertEqual(check(other)['frames'], FRAMES)

    def test_wrong_law_or_camera_is_rejected(self):
        other = copy.deepcopy(self.config)
        other['law_id'] = 'NRS-484B-307-9b'
        with self.assertRaisesRegex(ValueError, 'identity'):
            check(other)
        other = copy.deepcopy(self.config)
        other['cameras'][2]['width'] = 1024
        with self.assertRaisesRegex(ValueError, 'Four-camera'):
            check(other)

    def test_requested_entry_must_match_case(self):
        other = copy.deepcopy(self.config)
        other['pedestrian_enters_highway_requested'] = not other[
            'pedestrian_enters_highway_requested']
        with self.assertRaisesRegex(ValueError, 'comparison variable'):
            check(other)


if __name__ == '__main__':
    unittest.main()
