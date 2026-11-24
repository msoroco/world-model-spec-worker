"""Pinned offline check of exact authored crossing proposal."""

import json
from pathlib import Path
import unittest

from construction import CASES, VIEWS, check_proposals, proposal
from runner import check


class CrossingProposal(unittest.TestCase):
    def test_exact_case_and_map(self):
        config = json.loads(Path('config.json').read_text())
        receipt = check(config)
        self.assertEqual(receipt['frames'], 600)
        self.assertEqual(receipt['camera_views'], [row[0] for row in VIEWS])
        self.assertFalse(receipt['physical_signal_verified'])

    def test_all_four_comparison_variants(self):
        receipt = check_proposals()
        self.assertEqual(len(receipt['cases']), 4)
        self.assertEqual([proposal(s)['requested_pedestrian_indication'] for s in CASES],
                         ['walk', 'dont_walk', 'walk', 'dont_walk'])

    def test_reject_wrong_device_state(self):
        config = json.loads(Path('config.json').read_text())
        config['requested_pedestrian_indication'] = 'unobserved'
        with self.assertRaisesRegex(ValueError, 'contrary-device'):
            check(config)


if __name__ == '__main__':
    unittest.main()
