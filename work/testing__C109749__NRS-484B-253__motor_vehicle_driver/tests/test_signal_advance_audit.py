import sys
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from signal_advance_audit import audit, measure


def history(indicators, *, step_m=10):
    return [dict(frame=100 + i, time_s=i / 20,
                 ego={'position_xy_m': [i * step_m, 0]},
                 ego_heading_deg=20 if i == len(indicators) - 1 else 0,
                 ego_left_indicator=value)
            for i, value in enumerate(indicators)]


class SignalAdvanceAuditTests(unittest.TestCase):
    def test_observed_below_at_above_100_foot_probe(self):
        for step, expected in ((10, False), (30.48 / 3, True), (12, True)):
            with self.subTest(step=step):
                result = measure(history([False, True, True, True, True, True], step_m=step))
                self.assertEqual(result['probes']['30.48']['observable_distance_met'], expected)
                self.assertTrue(result['probes']['30.48']['full_signal_onset_observed'])
                self.assertFalse(result['legal_verdict_asserted'])

    def test_indicator_gap_resets_continuous_distance(self):
        result = measure(history([True, True, False, True, True, True], step_m=20))
        self.assertEqual(result['observed_continuous_approach_distance_m'], 20)
        self.assertFalse(result['probes']['30.48']['observable_distance_met'])
        result = measure(history([True, True, True, True, False], step_m=20))
        self.assertEqual(result['observed_continuous_approach_distance_m'], 0)

    def test_turn_segment_does_not_complete_advance_distance(self):
        result = measure(history([False, True, True, True, True], step_m=12))
        self.assertEqual(result['observed_continuous_approach_distance_m'], 24)
        self.assertEqual(result['last_prechange_frame'], 103)
        self.assertFalse(result['probes']['30.48']['observable_distance_met'])

    def test_active_at_capture_start_is_lower_bound(self):
        result = measure(history([True, True, True, True, True]))
        self.assertTrue(result['signal_active_at_capture_start'])
        self.assertFalse(result['probes']['30.48']['full_signal_onset_observed'])

    def test_missing_indicator_and_frame_gap_rejected(self):
        rows = history([True, True, True])
        del rows[1]['ego_left_indicator']
        with self.assertRaisesRegex(ValueError, 'indicator'):
            measure(rows)
        rows = history([True, True, True])
        rows[1]['frame'] += 3
        with self.assertRaisesRegex(ValueError, 'Nonconsecutive'):
            measure(rows)

    def test_unsealed_history_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'interaction_history.jsonl').write_text('\n'.join(map(json.dumps, history([True, True, True]))))
            (root / 'capture-seal.json').write_text(json.dumps({'sources': {'interaction_history.jsonl': 'stale'}}))
            with self.assertRaisesRegex(ValueError, 'capture seal'):
                audit(root)


if __name__ == '__main__':
    unittest.main()
