"""Geometry and case identity tests included in every exact bundle."""
import json
import unittest
from pathlib import Path
import os
import tempfile

from runner import load_case


class ExactOfflineCase(unittest.TestCase):
    def test_exact_geometry_and_signal(self):
        case = load_case()
        self.assertEqual(case['official_signal_aspects'], ['circular_green'])
        self.assertEqual(case['duration_frames'], 900)

    def test_wrong_region_is_rejected(self):
        case = load_case()
        if case['other_user_kind'] is None:
            case['other_user_kind'] = 'pedestrian'
        else:
            case['other_user_region_at_exhibition'] = 'outside' if case['other_user_region_at_exhibition'] != 'outside' else 'intersection'
        scratch = Path(tempfile.gettempdir()) / ('c111125-negative-' + str(os.getpid()) + '.json')
        try:
            scratch.write_text(json.dumps(case))
            with self.assertRaises(ValueError):
                load_case(scratch)
        finally:
            scratch.unlink(missing_ok=True)
