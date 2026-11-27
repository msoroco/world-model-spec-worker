"""Selected CPU capture contract checks; no original Native execution."""
import copy
import json
from pathlib import Path
import unittest

from runner import check
from roundabout_scene import LANES, intent


class ExactCaseOffline(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_exact_profile_and_alternative(self):
        result = check(self.config)
        self.assertEqual(result['frames'], 600)
        self.assertEqual(len(result['camera_names']), 4)
        case = self.config['selected_case_id'].split('__')[-1]
        self.assertIn(case, LANES)
        self.assertIn(intent(case), ('left_turn', 'u_turn'))
        self.assertFalse(result['native_executed'])

    def test_missing_camera_rejected(self):
        changed = copy.deepcopy(self.config)
        changed['cameras'].pop()
        with self.assertRaisesRegex(ValueError, 'Four source cameras'):
            check(changed)

    def test_short_capture_rejected(self):
        changed = copy.deepcopy(self.config)
        changed['frames'] = 599
        with self.assertRaisesRegex(ValueError, '30-second'):
            check(changed)

    def test_wrong_case_rejected(self):
        changed = copy.deepcopy(self.config)
        changed['selected_case_id'] += '_wrong'
        with self.assertRaisesRegex(ValueError, 'Unknown exact selected case'):
            check(changed)

    def test_legal_claim_rejected(self):
        changed = copy.deepcopy(self.config)
        changed['legal_verdict'] = 'compliant'
        with self.assertRaisesRegex(ValueError, 'Premature physical or legal claim'):
            check(changed)
