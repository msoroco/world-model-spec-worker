"""Independent delivery signal measurement rejects false source claims."""
import copy
import math
import sys
import unittest
from pathlib import Path

ASSIGNMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSIGNMENT))
from signal_advance_delivery_audit import measure_signal_sequence


class SignalAdvanceDeliveryAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def history(distance, interrupted=False):
            warmup = 32
            steps = math.ceil(distance / 0.25)
            turn = warmup + steps + 1
            rows = []
            for i in range(900):
                x = round((i - warmup - steps) * distance / steps, 9) if i < turn else 0.0
                lit = warmup <= i <= turn
                if interrupted and i == warmup + steps // 2:
                    lit = False
                rows.append({'frame': 50000 + i, 'time_s': (i + 1) / 20,
                             'ego': {'position_xy_m': [x, 0.0]},
                             'ego_heading_deg': 0.0 if i < turn else -20.0,
                             'ego_left_indicator': lit})
            return rows
        cls.histories = {'25_0': history(25.0),
                         '30_48': history(30.48),
                         'interrupted': history(36.0, interrupted=True)}

    @staticmethod
    def result(distance):
        return {'measured_values': {'observed_continuous_signal_advance_m': distance},
                'target_checks': [{'target': 'continuous_left_signal_at_least_30_48_m',
                                   'requested': True, 'measured': distance >= 30.48,
                                   'matched': distance >= 30.48}]}

    def test_exact_at_boundary_from_full_history(self):
        proof = measure_signal_sequence(self.histories['30_48'], self.result(30.48))
        self.assertEqual(proof['observed_continuous_approach_distance_m'], 30.48)
        self.assertTrue(proof['full_signal_onset_observed'])
        self.assertEqual(proof['turn_frame'], 50155)

    def test_below_boundary_rejected(self):
        with self.assertRaisesRegex(ValueError, 'below 30.48'):
            measure_signal_sequence(self.histories['25_0'], self.result(25.0))

    def test_interrupted_indicator_rejected(self):
        with self.assertRaisesRegex(ValueError, 'below 30.48'):
            measure_signal_sequence(self.histories['interrupted'], self.result(36.0))

    def test_changed_saved_measurement_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Saved signal distance'):
            measure_signal_sequence(self.histories['30_48'], self.result(31.0))

    def test_turn_segment_cannot_supply_missing_distance(self):
        rows = copy.deepcopy(self.histories['25_0'])
        turn = next(i for i, row in enumerate(rows) if row['ego_heading_deg'] < -15)
        rows[turn]['ego']['position_xy_m'] = [20.0, 0.0]
        with self.assertRaisesRegex(ValueError, 'below 30.48'):
            measure_signal_sequence(rows, self.result(25.0))

    def test_preturn_position_jump_rejected(self):
        rows = copy.deepcopy(self.histories['25_0'])
        rows[60]['ego']['position_xy_m'] = [rows[60]['ego']['position_xy_m'][0] + 20.0, 0.0]
        with self.assertRaisesRegex(ValueError, 'position jump'):
            measure_signal_sequence(rows, self.result(25.0))

    def test_frame_cadence_gap_rejected(self):
        rows = copy.deepcopy(self.histories['30_48'])
        rows[60]['time_s'] += 0.1
        with self.assertRaisesRegex(ValueError, '20 Hz frame cadence'):
            measure_signal_sequence(rows, self.result(30.48))

    def test_right_turn_rejected(self):
        rows = copy.deepcopy(self.histories['30_48'])
        for row in rows:
            if row['ego_heading_deg'] < 0:
                row['ego_heading_deg'] = -row['ego_heading_deg']
        with self.assertRaisesRegex(ValueError, 'left turn onset missing'):
            measure_signal_sequence(rows, self.result(30.48))


if __name__ == '__main__':
    unittest.main()
