import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'crest_geometry.py'
spec = importlib.util.spec_from_file_location('crest_geometry', MODULE)
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)


def lanes(height):
    stations = list(range(0, 101, 10))
    def make(lane_id, direction, y):
        return [{'s_m': s, 'x_m': s, 'y_m': y, 'road_z_m': height(s),
                 'road_id': 1, 'lane_id': lane_id, 'travel_direction': direction,
                 'source_ref': f'Native waypoint {lane_id}:{s}'} for s in stations]
    return make(1, 'increasing_s', 0), make(-1, 'decreasing_s', 3)


class CrestGeometryTests(unittest.TestCase):
    def test_real_grade_intersects_proxy_ray_from_both_approaches(self):
        ego, other = lanes(lambda s: 8 if s == 50 else 0)
        self.assertTrue(geometry.crest_occlusion(ego, other, observer_s_m=10,
                                                 target_s_m=90)['sampled_grade_blocks_proxy_ray'])
        reverse_ego = [{**p, 's_m': 100-p['s_m'], 'travel_direction': 'increasing_s'} for p in reversed(other)]
        reverse_other = [{**p, 's_m': 100-p['s_m'], 'travel_direction': 'decreasing_s'} for p in reversed(ego)]
        self.assertTrue(geometry.crest_occlusion(reverse_ego, reverse_other,
                                                 observer_s_m=10, target_s_m=90)['sampled_grade_blocks_proxy_ray'])

    def test_flat_grade_does_not_fake_obstruction(self):
        ego, other = lanes(lambda s: 0)
        self.assertFalse(geometry.crest_occlusion(ego, other, observer_s_m=10,
                                                  target_s_m=90)['sampled_grade_blocks_proxy_ray'])

    def test_rejects_wrong_opposing_lane_and_missing_source(self):
        ego, other = lanes(lambda s: 0)
        other[0]['travel_direction'] = 'increasing_s'
        with self.assertRaisesRegex(ValueError, 'directions'):
            geometry.validate_lanes(ego, other)
        other[0]['travel_direction'] = 'decreasing_s'
        ego[0]['source_ref'] = ''
        with self.assertRaisesRegex(ValueError, 'provenance'):
            geometry.validate_lanes(ego, other)


if __name__ == '__main__':
    unittest.main()
