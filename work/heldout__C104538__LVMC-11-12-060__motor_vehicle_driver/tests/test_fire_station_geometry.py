import math
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fire_station_geometry import classify_path, validate_entrance


def wp(x, y, lane):
    return SimpleNamespace(road_id=7 if lane == 1 else 8, lane_id=lane,
                           transform=SimpleNamespace(location=SimpleNamespace(x=x, y=y)))


SOURCE = {'kind': 'operator_survey', 'asset_id': 'test-fire-station',
          'source_sha256': '0' * 64}


class EntranceGeometryTest(unittest.TestCase):
    def geometry(self):
        return validate_entrance(wp(-8, 0, 1), wp(0, 0, 1), wp(8, 0, 1),
                                 wp(0, 6, 2), source=SOURCE)

    def test_requires_real_branch_and_source(self):
        g = self.geometry()
        self.assertEqual(g['branch_angle_deg'], 90)
        self.assertNotEqual(g['public_lane'], g['driveway_lane'])
        with self.assertRaisesRegex(ValueError, 'source-bound'):
            validate_entrance(wp(-8, 0, 1), wp(0, 0, 1), wp(8, 0, 1),
                              wp(0, 6, 2), source={})
        with self.assertRaisesRegex(ValueError, 'physical branch angle'):
            validate_entrance(wp(-8, 0, 1), wp(0, 0, 1), wp(8, 0, 1),
                              wp(6, 0, 2), source=SOURCE)

    def test_distinguishes_front_turn_from_driveway_use(self):
        g = self.geometry()
        public = [{'frame': 1, 'x_m': -5, 'y_m': 0, 'heading_rad': 0, 'lane_id': (7, 1)},
                  {'frame': 2, 'x_m': 0, 'y_m': 0, 'heading_rad': math.pi / 2, 'lane_id': (7, 1)},
                  {'frame': 3, 'x_m': -5, 'y_m': 0, 'heading_rad': math.pi, 'lane_id': (7, 1)}]
        front = classify_path(public, g)
        self.assertTrue(front['reversal_observed'])
        self.assertFalse(front['entered_driveway'])
        driveway = [dict(row) for row in public]
        driveway[1]['lane_id'] = (8, 2)
        self.assertTrue(classify_path(driveway, g)['entered_driveway'])
        with self.assertRaisesRegex(ValueError, 'frame identities'):
            classify_path(public[:2] + [public[1]], g)


if __name__ == '__main__':
    unittest.main()
