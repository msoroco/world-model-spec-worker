"""Both-approach Native route geometry checks for the 500 ft branch."""
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from u_turn_407_geometry import candidate_screen, inspect_407_geometry, select_407_candidate, validate_geometry_packet


class Waypoint:
    lane_type = 'Driving'
    road_id = 7

    def __init__(self, lane_id, n, curve=False, crest=False, stop_at=None):
        self.lane_id = lane_id
        self.n = n
        self.curve = curve
        self.crest = crest
        self.stop_at = stop_at
        x = -10.0*n if lane_id < 0 else 10.0*n
        y = 3.0 if lane_id < 0 else -3.0
        if curve:
            y += (n/23.0)**2 * 45.0
        z = 0.0 if not crest else 1.5 * max(0.0, 1.0-abs(n-8)/8)
        self.transform = SimpleNamespace(location=SimpleNamespace(x=x, y=y, z=z))

    def previous(self, distance):
        if self.stop_at is not None and self.n >= self.stop_at:
            return []
        if distance != 10.0:
            raise ValueError('Unexpected sample distance')
        return [Waypoint(self.lane_id, self.n+1, self.curve, self.crest, self.stop_at)]


class GeometryTests(unittest.TestCase):
    def test_both_directions_retain_full_native_route_and_curve(self):
        scene = {'approach': Waypoint(-1, 0, curve=True),
                 'opposite': Waypoint(1, 0, crest=True)}
        result = inspect_407_geometry(scene)
        self.assertIsNone(result['both_direction_body_ray_visibility'])
        self.assertFalse(result['physical_occlusion_verified'])
        self.assertTrue(candidate_screen(result))
        self.assertEqual(set(result['directions']), {'approach', 'opposite'})
        self.assertTrue(all(len(side['samples']) == 24 for side in result['directions'].values()))
        self.assertAlmostEqual(result['directions']['approach']['probe_xyz_m'][0], -152.4)
        self.assertAlmostEqual(result['directions']['opposite']['probe_xyz_m'][0], 152.4)
        self.assertGreater(result['directions']['approach']['cumulative_deflection_deg'], 8.0)
        self.assertGreater(result['directions']['opposite']['crest_prominence_m'], 0.5)

    def test_straight_flat_geometry_is_not_candidate(self):
        result = inspect_407_geometry({'approach': Waypoint(-1, 0), 'opposite': Waypoint(1, 0)})
        self.assertFalse(candidate_screen(result))

    def test_short_or_ambiguous_route_rejected_for_either_direction(self):
        for lane_id in (-1, 1):
            scene = {'approach': Waypoint(-1, 0), 'opposite': Waypoint(1, 0)}
            scene['approach' if lane_id < 0 else 'opposite'] = Waypoint(lane_id, 0, stop_at=12)
            with self.assertRaisesRegex(ValueError, 'route missing or ambiguous'):
                inspect_407_geometry(scene)

    def test_candidate_search_skips_flat_and_short_routes(self):
        flat = {'approach': Waypoint(-1, 0), 'opposite': Waypoint(1, 0)}
        short = {'approach': Waypoint(-1, 0, stop_at=12), 'opposite': Waypoint(1, 0)}
        curved = {'approach': Waypoint(-1, 0, curve=True), 'opposite': Waypoint(1, 0)}
        scenes = [flat, short, curved]

        def get_scene(_, **kwargs):
            index = kwargs['candidate_index']
            if index >= len(scenes):
                raise ValueError('No requested Native opposing-lane U-turn pair')
            return scenes[index]

        with patch('u_turn_construction.select_u_turn_scene', side_effect=get_scene):
            selected, report = select_407_candidate(object())
        self.assertIs(selected, curved)
        self.assertEqual(report['candidate_index'], 2)

    def test_saved_geometry_recalculation_and_tamper(self):
        scene = {'approach': Waypoint(-1,0,curve=True),
                 'opposite': Waypoint(1,0,crest=True)}
        report = inspect_407_geometry(scene)
        context = {'approach_road_id':7,'approach_lane_id':-1,
                   'opposite_lane_id':1}
        self.assertEqual(validate_geometry_packet(report,context),report)
        report['directions']['approach']['probe_xyz_m'][0] += 1
        with self.assertRaisesRegex(ValueError,'metric differs'):
            validate_geometry_packet(report,context)


if __name__ == '__main__':
    unittest.main()
