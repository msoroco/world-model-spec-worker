import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'pass_right_route.py'
spec = importlib.util.spec_from_file_location('pass_right_route', MODULE)
route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(route)


def map_packet():
    return {'source_kind': 'original_native_map_geometry', 'direction': 'two_way',
            'same_direction_marked_lanes': 1, 'intersection_s_m': [55.0, 70.0],
            'actor_half_width_m': 0.9, 'right_pass_center_m': 3.0,
            'target_lane_center_m': 0.0, 'turn_lateral_displacement_m': 1.2,
            'cross_sections': [{'station_m': s, 'source': 'native_map',
                                'right_positive': True, 'paved_lateral_bounds_m': [-2.0, 4.5]}
                               for s in range(45, 81, 5)]}


class TestRoute(unittest.TestCase):
    def test_variants_change_only_target_instruction(self):
        built = [route.build_case(map_packet(), v) for v in ('left_signal', 'left_turn', 'neither')]
        self.assertEqual(len({json.dumps(x['ego_path_s_lateral_m']) for x in built}), 1)
        self.assertEqual([x['target_left_signal_request'] for x in built], [True, False, False])
        self.assertEqual([x['target_turn_request'] for x in built], [False, True, False])
        self.assertNotEqual(built[1]['target_path_s_lateral_m'], built[0]['target_path_s_lateral_m'])

    def test_rejects_narrow_or_wrong_direction(self):
        x = map_packet(); x['cross_sections'][3]['paved_lateral_bounds_m'][1] = 3.5
        with self.assertRaisesRegex(ValueError, 'footprint exceeds'):
            route.build_case(x, 'left_signal')
        x = map_packet(); x['direction'] = 'one_way'
        with self.assertRaisesRegex(ValueError, 'road direction'):
            route.build_case(x, 'left_signal')

    def test_rejects_missing_map_stations_and_source(self):
        x = map_packet(); x['cross_sections'].pop()
        with self.assertRaisesRegex(ValueError, 'cross sections'):
            route.build_case(x, 'left_signal')
        x = map_packet(); x['cross_sections'][0]['source'] = 'requested_target'
        with self.assertRaisesRegex(ValueError, 'native provenance'):
            route.build_case(x, 'left_signal')

    def test_source_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'map.json'; p.write_text(json.dumps(map_packet()))
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(route.load_map_packet(p, digest)['direction'], 'two_way')
            with self.assertRaisesRegex(ValueError, 'sha256 mismatch'):
                route.load_map_packet(p, 'f' * 64)
            x = map_packet(); x['source_kind'] = 'synthetic_geometry'; p.write_text(json.dumps(x))
            with self.assertRaisesRegex(ValueError, 'original Native'):
                route.load_map_packet(p, hashlib.sha256(p.read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()
