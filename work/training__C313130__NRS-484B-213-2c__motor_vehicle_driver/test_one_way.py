"""Offline checks on the materialized exact one-way tunnel bundle."""

import json
from pathlib import Path
import unittest

from runner import check
from measure_tunnel import measure


class OneWayTunnelTest(unittest.TestCase):
    def setUp(self):
        self.bundle = Path(__file__).resolve().parents[1]

    def test_exact_bundle(self):
        self.assertEqual(check(self.bundle)["frames"], 600)

    def test_original_source_required(self):
        source = {"source_kind": "original_native_tunnel_map_and_ray_readback",
                  "structure_kind": "tunnel", "approach_portal_x_m": 0,
                  "highway_centre_y_m": -3.5, "one_way_native_survey": True}
        with self.assertRaisesRegex(ValueError, "Missing source hash"):
            measure(source, [])

    def test_one_way_road_lane_ids(self):
        self.assertIn('id="-2" type="driving"',
                      (self.bundle / "road.xodr").read_text())


if __name__ == "__main__":
    unittest.main()
