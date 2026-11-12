import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from listener_sweep_placement import listener_points


class ListenerSweepPlacementTests(unittest.TestCase):
    def test_three_route_relative_positions_in_both_directions(self):
        east = listener_points([(-2, 0), (0, 0), (2, 0)])
        west = listener_points([(2, 0), (0, 0), (-2, 0)])
        self.assertEqual([row['point_y_m'] for row in east], [2, 4, 6])
        self.assertEqual([row['point_y_m'] for row in west], [-2, -4, -6])
        self.assertEqual([row['nearest_sampled_route_m'] for row in east], [2, 4, 6])

    def test_rejects_degenerate_route_and_invalid_offsets(self):
        with self.assertRaisesRegex(ValueError, 'tangent is degenerate'):
            listener_points([(0, 0), (0, 0), (0, 0)])
        with self.assertRaisesRegex(ValueError, 'increasing positive offsets'):
            listener_points([(-2, 0), (0, 0), (2, 0)], (2, 2, 6))
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            listener_points([(-2, 0), (0, float('nan')), (2, 0)])


if __name__ == '__main__':
    unittest.main()
