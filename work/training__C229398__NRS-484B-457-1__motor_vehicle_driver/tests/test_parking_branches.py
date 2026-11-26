"""Exercise authored branch geometry and diagnostic source requirements."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from parking_scene import CASES, check, request
from prove_parking_branches import fixture
from measure_parking import measure


class ParkingBranches(unittest.TestCase):
    def test_all_exact_requests(self):
        for case in CASES:
            with self.subTest(case=case):
                item = request(case)
                self.assertTrue(check(item)['passed'])
                self.assertEqual(item['roadway_lanes']['same_direction_driving'], [-1, -2])

    def test_source_shaped_measurements(self):
        for case, (kind, gap, angle, _) in CASES.items():
            with self.subTest(case=case):
                context, rows = fixture(kind, gap, angle)
                result = measure(context, rows)
                self.assertEqual(result['parking_kind'], kind)
                self.assertEqual(result['legal_compliance'], 'unassessed')
                self.assertFalse(result['original_native_observed'])

    def test_missing_authority_rejected(self):
        context, rows = fixture('angle_dot')
        context.pop('dot_width_determination_sha256')
        with self.assertRaisesRegex(ValueError, 'dot_width_determination'):
            measure(context, rows)


if __name__ == '__main__':
    unittest.main()
