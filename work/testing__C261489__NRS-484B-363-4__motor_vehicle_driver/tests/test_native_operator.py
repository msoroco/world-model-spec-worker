"""Exercise source geometry used to measure original Native passing order."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_operator import progress, transform


class NativeOperatorTests(unittest.TestCase):
    def test_common_route_station_preserves_vehicle_order(self):
        route = [[10, 0], [30, 2], [50, 2], [70, 0]]
        ego_station = progress([10, 0], route)
        target_station = progress([20, 0], route)
        self.assertLess(ego_station, target_station)
        self.assertAlmostEqual(progress([50, 2], route), 40.1, places=0)

    def test_missing_native_transform_rejected(self):
        class FakeCarla:
            pass
        with self.assertRaisesRegex(ValueError, "transform incomplete"):
            transform(FakeCarla, {"x": 1, "y": 2, "yaw": 0})


if __name__ == "__main__":
    unittest.main()
