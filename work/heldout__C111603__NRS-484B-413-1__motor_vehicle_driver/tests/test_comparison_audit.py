import sys
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from comparison_audit import CHANGED, audit, load_case


class ComparisonAuditTests(unittest.TestCase):
    def test_all_five_source_bound_comparisons(self):
        for comparison_id in CHANGED:
            with self.subTest(comparison_id=comparison_id):
                report = audit(comparison_id)
                self.assertEqual(report['case_ids'], audit(comparison_id)['case_ids'])
                self.assertFalse(report['physical_acceptance_claimed'])

    def test_rejects_changed_fixed_original(self):
        pair = audit('vehicle_indicator')['case_ids']
        with self.assertRaisesRegex(ValueError, 'Fixed original comparison source differs'):
            audit('vehicle_indicator', pair[1], {'ego_turn_motion.jsonl': '{}\n'})

    def test_rejects_missing_declared_difference(self):
        pair = audit('vehicle_indicator')['case_ids']
        first, _, _ = load_case(pair[0])
        with self.assertRaisesRegex(ValueError, 'Declared original comparison difference is absent'):
            audit('vehicle_indicator', pair[1],
                  {'ego_signal_audio.jsonl': first['ego_signal_audio.jsonl']})

    def test_listener_rms_joins_original_packets_before_turn(self):
        report = audit('pedestrian_horn_audio')
        self.assertGreater(report['measured_values']['pre_turn_listener_rms'][0], 0)
        self.assertEqual(report['measured_values']['pre_turn_listener_rms'][1], 0)
        case = report['case_ids'][0]
        files, _, _ = load_case(case)
        packets = [json.loads(row) for row in files['listener_audio_original.jsonl'].splitlines()]
        packets[2]['samples'][0] = 0.8
        changed = ''.join(json.dumps(row) + '\n' for row in packets)
        with self.assertRaisesRegex(ValueError, 'packet hash or signal projection'):
            audit('pedestrian_horn_audio', case, {'listener_audio_original.jsonl': changed})

    def test_listener_rms_rejects_missing_frame_and_invalid_sample(self):
        case = audit('pedestrian_horn_audio')['case_ids'][0]
        files, _, _ = load_case(case)
        packets = [json.loads(row) for row in files['listener_audio_original.jsonl'].splitlines()]
        packets[2]['frame'] += 100
        with self.assertRaisesRegex(ValueError, 'frame join differs'):
            audit('pedestrian_horn_audio', case, {'listener_audio_original.jsonl': ''.join(json.dumps(row) + '\n' for row in packets)})
        packets[2]['frame'] -= 100
        packets[2]['samples'][0] = float('nan')
        with self.assertRaisesRegex(ValueError, 'samples are invalid'):
            audit('pedestrian_horn_audio', case, {'listener_audio_original.jsonl': ''.join(json.dumps(row) + '\n' for row in packets)})


if __name__ == '__main__':
    unittest.main()
