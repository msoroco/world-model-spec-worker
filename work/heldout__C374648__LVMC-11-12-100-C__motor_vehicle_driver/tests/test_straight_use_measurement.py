"""Original-source straight-use checks; no physical or legal acceptance."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from straight_use_measurement import measure
from test_turn_origin_finalizer import sources


def straight_source(root, *, outer=False):
    sources(root)
    path = root/'turn_origin_native.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    for row in rows:
        row['ego_forward_xy'] = [1, 0]
        if outer:
            row['lane_id'] = 2
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    return path


class StraightUseMeasurementTests(unittest.TestCase):
    def test_center_and_outer_straight_origins(self):
        for outer in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                value = measure(straight_source(Path(directory), outer=outer))
                self.assertEqual(value['origin_matches_center_lane'], not outer)
                self.assertTrue(value['straight_motion_observed'])
                self.assertEqual(value['maximum_deflection_deg'], 0)
                self.assertFalse(value['designation_authority_verified'])

    def test_turning_and_missing_original_reject(self):
        with tempfile.TemporaryDirectory() as directory:
            path = straight_source(Path(directory))
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[-1]['ego_forward_xy'] = [0, -1]
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'not straight'):
                measure(path)
            path.unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                measure(path)
