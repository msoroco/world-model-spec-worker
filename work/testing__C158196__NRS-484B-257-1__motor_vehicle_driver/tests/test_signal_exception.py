import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from test_nearest_view import write_attempt

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('signal_exception_c158196', ROOT / 'signal_exception.py')
signal_exception = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signal_exception)
comparison_spec = importlib.util.spec_from_file_location('saved_comparison_c158196_signal', ROOT / 'saved_comparison.py')
saved_comparison = importlib.util.module_from_spec(comparison_spec)
comparison_spec.loader.exec_module(saved_comparison)


def active_attempt(root):
    packet_path = write_attempt(root, 'active_signal_exception',
                                policy='observe_signal_governance', minimum_speed=2.0)
    packet = json.loads(packet_path.read_text(encoding='utf-8'))
    packet['context']['signal_controlling'] = True
    frames = [row['frame'] for row in packet['frames']]
    source = root / packet['sources']['signal_state_readback']['path']
    source.write_text(json.dumps({'source_kind': 'original_native_signal_readback',
                                  'device_kind': 'traffic_control_signal',
                                  'governs_ego_approach': True,
                                  'observed_frame_ids': frames}) + '\n', encoding='utf-8')
    packet['sources']['signal_state_readback']['sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    packet_path.write_text(json.dumps(packet, sort_keys=True) + '\n', encoding='utf-8')
    return packet_path


class SignalExceptionTests(unittest.TestCase):
    def test_saved_signal_governance_and_fixed_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            left, right = Path(tmp) / 'yield', Path(tmp) / 'signal'
            write_attempt(left, 'nearest_view_continue',
                          policy='continue_through_observed_traffic', minimum_speed=2.0)
            active = active_attempt(right)
            proof = signal_exception.measure(json.loads(active.read_text()), right)
            self.assertEqual(proof['frame_count'], 7)
            self.assertTrue(proof['subsection_1_exception_observed'])
            result = saved_comparison.audit(left, right, 'governing_signal_exception')
            self.assertEqual(result['right']['signal_state_source_sha256'],
                             proof['signal_state_source_sha256'])
            self.assertEqual(result['status'], 'source_bound_measured_not_legal_verdict')

    def test_rejects_stale_signal_and_changed_fixed_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            left, right = Path(tmp) / 'yield', Path(tmp) / 'signal'
            write_attempt(left, 'nearest_view_continue',
                          policy='continue_through_observed_traffic', minimum_speed=2.0)
            active = active_attempt(right)
            source = right / 'native' / 'signal_state_readback.json'
            source.write_text('changed\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
                saved_comparison.audit(left, right, 'governing_signal_exception')
            active = active_attempt(right)
            packet = json.loads(active.read_text())
            packet['context']['near_side_crosswalk'] = True
            active.write_text(json.dumps(packet) + '\n')
            with self.assertRaisesRegex(ValueError, 'site geometry'):
                saved_comparison.audit(left, right, 'governing_signal_exception')
            active = active_attempt(right)
            packet = json.loads(active.read_text())
            fixed_source = right / packet['sources']['native_map']['path']
            fixed_source.write_text('different native map bytes\n', encoding='utf-8')
            packet['sources']['native_map']['sha256'] = hashlib.sha256(fixed_source.read_bytes()).hexdigest()
            active.write_text(json.dumps(packet) + '\n')
            with self.assertRaisesRegex(ValueError, 'fixed signal-comparison source differs'):
                saved_comparison.audit(left, right, 'governing_signal_exception')

    def test_rejects_partial_signal_frame_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet_path = active_attempt(root)
            packet = json.loads(packet_path.read_text())
            source = root / packet['sources']['signal_state_readback']['path']
            state = json.loads(source.read_text())
            state['observed_frame_ids'].pop()
            source.write_text(json.dumps(state) + '\n')
            packet['sources']['signal_state_readback']['sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'does not span'):
                signal_exception.measure(packet, root)


if __name__ == '__main__':
    unittest.main()
