"""Three-actor diagnostic shapes only, never original physical evidence."""
import copy
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reciprocal_witness import measure_later_opponent


def body(x):
    return [[x + dx, y, z] for z in (-0.5, 0.5)
            for dx in (-0.5, 0.5) for y in (-0.5, 0.5)]


def rows():
    result = []
    for index in range(4):
        result.append({'frame': 100 + index, 'time_s': index / 20,
                       'ego_actor_id': 1, 'opponent_actor_id': 2,
                       'later_opponent_actor_id': 3,
                       'opponent_vertices': body(0 if index == 0 else 10),
                       'later_opponent_vertices': body(10 if index < 3 else 0),
                       'ego_heading': [1, 0], 'later_opponent_heading': [-1, 0],
                       'ego_turn_committed': index >= 2,
                       'later_opponent_speed_mps': 4 if index < 2 else 2,
                       'later_opponent_braking': index == 2,
                       'later_opponent_driver_control_source': 'original get_control'})
    return result


class ReciprocalWitnessTests(unittest.TestCase):
    def setUp(self):
        self.polygon = [[-5, -5], [5, -5], [5, 5], [-5, 5]]

    def test_source_bound_three_actor_event_order(self):
        observed = measure_later_opponent(rows(), self.polygon,
                                          expected_braking=True)
        self.assertEqual(observed['later_opponent_actor_id'], 3)
        self.assertEqual(observed['initial_clear_frame'], 101)
        self.assertEqual(observed['ego_commit_frame'], 102)
        self.assertEqual(observed['later_intersection_frame'], 103)
        self.assertEqual(observed['legal_right_of_way'], 'unresolved')

    def test_rejects_alias_drift_missing_source_and_wrong_response(self):
        for change, error in (
            (lambda r: r[2].update(later_opponent_actor_id=2), 'distinct'),
            (lambda r: r[2].update(later_opponent_actor_id=4), 'drift'),
            (lambda r: r[2].pop('later_opponent_driver_control_source'), 'control'),
            (lambda r: r[3].update(later_opponent_braking=True), 'response'),
            (lambda r: r[3].update(later_opponent_vertices=body(10)), 'order'),
            (lambda r: r[0].update(opponent_vertices=body(10)), 'order'),
        ):
            source = copy.deepcopy(rows())
            change(source)
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                measure_later_opponent(source, self.polygon,
                                       expected_braking=False if error == 'response' else True)

    def test_rejects_wrong_clock_and_wrong_opposing_heading(self):
        source = rows()
        source[2]['time_s'] += 0.1
        with self.assertRaisesRegex(ValueError, '20 Hz'):
            measure_later_opponent(source, self.polygon, expected_braking=True)
        source = rows()
        source[2]['later_opponent_heading'] = [1, 0]
        with self.assertRaisesRegex(ValueError, 'opposite-direction'):
            measure_later_opponent(source, self.polygon, expected_braking=True)


if __name__ == '__main__':
    unittest.main()
