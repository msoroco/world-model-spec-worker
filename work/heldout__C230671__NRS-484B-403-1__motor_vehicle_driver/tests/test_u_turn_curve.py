import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from u_turn_curve import curve_profile, select_curved_u_turn_scene


class Waypoint:
    def __init__(self, index, yaw, lane=-1):
        self.road_id, self.lane_id, self.is_junction = 7, lane, False
        self.lane_type = 'Driving'
        radians = math.radians(yaw)
        self.transform = SimpleNamespace(
            location=SimpleNamespace(x=5.0 * index, y=0.0),
            get_forward_vector=lambda: SimpleNamespace(
                x=math.cos(radians), y=math.sin(radians)))
        self.later = []
        self.left = None

    def next(self, spacing):
        assert spacing == 5.0
        return self.later

    def get_left_lane(self):
        return self.left

    def get_right_lane(self):
        return None


class CurveTests(unittest.TestCase):
    def scene(self, last_yaw):
        nodes = [Waypoint(i, last_yaw * i / 6) for i in range(7)]
        for a, b in zip(nodes, nodes[1:]):
            a.later = [b]
        nodes[0].left = Waypoint(0, 180, lane=1)
        return SimpleNamespace(generate_waypoints=lambda spacing: nodes[:1]), nodes

    def test_native_curve_geometry_retains_unknown_visibility(self):
        mapping, nodes = self.scene(18)
        profile = curve_profile(nodes[0])
        self.assertAlmostEqual(profile['net_heading_change_deg'], 18)
        self.assertIsNone(profile['driver_view_500ft_status'])
        self.assertIsNone(profile['statutory_407_applicability'])
        selected = select_curved_u_turn_scene(mapping)
        self.assertEqual(selected['road_id'], 7)
        self.assertEqual(selected['curve_profile'], profile)

    def test_straight_and_discontinuous_source_rejected(self):
        mapping, nodes = self.scene(0)
        with self.assertRaisesRegex(ValueError, 'No requested Native curved'):
            select_curved_u_turn_scene(mapping)
        nodes[2].later = []
        with self.assertRaisesRegex(ValueError, 'continuity missing'):
            curve_profile(nodes[0])


if __name__ == '__main__':
    unittest.main()
