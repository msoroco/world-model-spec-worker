import copy
import json
import unittest
from pathlib import Path
from runner import check

class ExactSourceCapture(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_exact_600_frame_source_plan(self):
        proof = check(self.config)
        self.assertEqual((proof['frames'], proof['rate_hz']), (600, 20))
        self.assertEqual(len(proof['cameras']), 4)
        self.assertFalse(proof['legal_verdict_claimed'])

    def test_reject_source_or_identity_change(self):
        for key, value in [('requested_signal_distance_m', 1),
                           ('weather', 'snow'), ('cell_id', 'other'),
                           ('duration_s', 1)]:
            bad = copy.deepcopy(self.config)
            bad[key] = value
            with self.assertRaises(ValueError):
                check(bad)
        bad = copy.deepcopy(self.config)
        bad['cameras'].pop()
        with self.assertRaises(ValueError):
            check(bad)
