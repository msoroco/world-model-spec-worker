import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('signal_approach', ROOT / 'signal_approach.py')
signal = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = signal
spec.loader.exec_module(signal)
native_spec = importlib.util.spec_from_file_location('native_signal', ROOT / 'native_signal.py')
native = importlib.util.module_from_spec(native_spec)
native_spec.loader.exec_module(native)


def scene(case):
    return {
        'incoming_route_xy': [[0.0, 0.0], [100.0, 0.0]],
        'signal_xy': [60.0, 4.0],
        'halt_target_xy': [60.0 + (case.metres + 2.0 if case.relation == 'downstream' else -case.metres - 2.0), 0.0],
        'body_front_offset_m': 2.0,
        'highway_public_use_reviewed': True,
        'signal_governed_route_reviewed': True,
        'signal_placement_authority_reviewed': True,
        'signal_stop_proceed_function_reviewed': True,
        'signal_official_status': case.signal_status,
        'signal_id': 'signal-001', 'signal_actor_id': '101',
        'ego_blueprint': 'vehicle.test', 'traffic_actor_blueprint': 'vehicle.test',
        'traffic_route_xy': [[20.0, 3.0], [90.0, 3.0]],
        'halt_activity': case.activity, 'exception_context': case.exception,
        'conflict_actor_route_xy': [[30.0, 2.0], [70.0, 2.0]],
        'conflict_necessity_source': 'original traffic motion',
        'direction_document_source': 'original authority record',
        'direction_document_type': case.exception,
    }


class SignalConstructionTests(unittest.TestCase):
    def test_all_exact_geometry(self):
        for case in signal.CASES:
            with self.subTest(case=case.name):
                measured = signal.validate_scene(scene(case), case)
                expected = case.metres + 2.0 if case.relation == 'upstream' else -case.metres - 2.0
                self.assertAlmostEqual(measured['target_signed_approach_station_m'], expected)
                self.assertEqual(measured['statutory_quantity_m'], 9.144)

    def test_wrong_approach_and_side_rejected(self):
        case = signal.CASES[0]
        wrong = scene(case)
        wrong['halt_target_xy'] = [69.0, 0.0]
        with self.assertRaisesRegex(ValueError, 'approach side'):
            signal.validate_scene(wrong, case)
        wrong = scene(case)
        wrong['signal_xy'] = [60.0, 0.0]
        with self.assertRaisesRegex(ValueError, 'highway side'):
            signal.validate_scene(wrong, case)

    def test_reverse_lane_uses_actual_heading(self):
        case = signal.CASES[0]
        reverse = scene(case)
        reverse['incoming_route_xy'] = [[100.0, 0.0], [0.0, 0.0]]
        reverse['signal_xy'] = [40.0, -4.0]
        reverse['halt_target_xy'] = [51.0, 0.0]
        self.assertAlmostEqual(signal.validate_scene(reverse, case)[
            'target_signed_approach_station_m'], 11.0)

    def test_official_and_direction_sources_rejected(self):
        case = signal.CASES[0]
        wrong = scene(case)
        wrong['signal_placement_authority_reviewed'] = False
        with self.assertRaisesRegex(ValueError, 'placement authority'):
            signal.validate_scene(wrong, case)
        case = signal.CASES[-1]
        wrong = scene(case)
        wrong['direction_document_source'] = ''
        with self.assertRaisesRegex(ValueError, 'direction document'):
            signal.validate_scene(wrong, case)

    def test_body_vertices_preserve_both_datums(self):
        measured = signal.signed_body_station([[50.0, 0.0], [54.0, 0.0],
                                                [54.0, 2.0], [50.0, 2.0]],
                                               (0.0, 0.0), (1.0, 0.0), 60.0)
        self.assertEqual(measured['body_front_approach_gap_m'], 6.0)
        self.assertEqual(measured['body_rear_approach_gap_m'], 10.0)

    def test_original_packet_missing_rejected(self):
        with self.assertRaisesRegex(ValueError, 'original reviewed signal packet missing'):
            signal.reviewed_packet(ROOT / 'nonexistent-source.json',
                                   signal.ASSIGNMENT + '__approach_below_30ft_park')

    def test_live_signal_readback_requires_actor_and_location(self):
        class Pose:
            location = type('Location', (), {'x': 60.0, 'y': 4.0})()
        class Actor:
            type_id = 'traffic.traffic_light'
            def get_transform(self):
                return Pose()
        class Actors:
            def find(self, actor_id):
                self.actor_id = actor_id
                return Actor()
        class World:
            actors = Actors()
            def get_actors(self):
                return self.actors
        source = scene(signal.CASES[0])
        self.assertEqual(native.read_signal(World(), source).type_id,
                         'traffic.traffic_light')
        source['signal_xy'] = [65.0, 4.0]
        with self.assertRaisesRegex(ValueError, 'placement differs'):
            native.read_signal(World(), source)


if __name__ == '__main__':
    unittest.main()
