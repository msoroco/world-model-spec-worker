import importlib.util
import json
import hashlib
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'pass_right_measure.py'
spec = importlib.util.spec_from_file_location('pass_right_measure', MODULE)
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)


def trace(mode='signal'):
    frames = []
    for i in range(12):
        frames.append({
            'frame': i, 't_s': i / 20, 'ego_s_m': 55 + 0.7 * i,
            'target_s_m': 59 + 0.15 * i, 'ego_lateral_m': 3.2,
            'target_lateral_m': -0.15 * i if mode == 'turn' else 0.0,
            'ego_speed_mps': 14.0, 'target_speed_mps': 3.0,
            'target_left_signal': mode == 'signal',
            'target_heading_deg': -3.0 * i if mode == 'turn' else 0.0,
            'ego_paved': True, 'target_paved': True,
        })
    return {'source_kind': 'original_native_actor_trace', 'fps': 20,
            'ego_id': 1, 'target_id': 2,
            'road': {'public_highway_observed': True, 'two_way_observed': True,
                     'intersection_s_m': [55, 70], 'actor_half_width_m': 0.9}, 'frames': frames}


class TestPassRight(unittest.TestCase):
    def test_signal_and_motion_are_distinct(self):
        a = measure.observe(trace('signal'))
        b = measure.observe(trace('turn'))
        c = measure.observe(trace('none'))
        self.assertEqual((a['target_left_signal_during_pass'], a['target_left_motion_during_pass']), (True, False))
        self.assertEqual((b['target_left_signal_during_pass'], b['target_left_motion_during_pass']), (False, True))
        self.assertFalse(c['paragraph_a_condition_observed'])
        self.assertEqual(c['legal_outcome'], 'unresolved')

    def test_rejects_no_pass_and_wrong_side(self):
        x = trace()
        for f in x['frames']:
            f['ego_s_m'] = 40
        with self.assertRaisesRegex(ValueError, 'no completed'):
            measure.observe(x)
        x = trace()
        x['frames'][7]['ego_lateral_m'] = -3
        with self.assertRaisesRegex(ValueError, 'not to target right'):
            measure.observe(x)
        x = trace()
        x['frames'][7]['ego_lateral_m'] = 1.5
        with self.assertRaisesRegex(ValueError, 'not to target right'):
            measure.observe(x)

    def test_rejects_missing_native_and_false_intersection(self):
        x = trace()
        del x['frames'][0]['target_left_signal']
        with self.assertRaisesRegex(ValueError, 'missing native actor field'):
            measure.observe(x)
        x = trace()
        x['road']['intersection_s_m'] = [100, 120]
        with self.assertRaisesRegex(ValueError, 'not at source-bound intersection'):
            measure.observe(x)
        x = trace(); del x['road']['actor_half_width_m']
        with self.assertRaisesRegex(ValueError, 'source actor footprint'):
            measure.observe(x)

    def test_seal_and_original_source_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'trace.json'
            p.write_text(json.dumps(trace()))
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertTrue(measure.observe(measure.load_sealed_trace(p, digest))['right_pass_observed'])
            with self.assertRaisesRegex(ValueError, 'sha256 mismatch'):
                measure.load_sealed_trace(p, '0' * 64)
            x = trace(); x['source_kind'] = 'requested_targets'
            p.write_text(json.dumps(x))
            with self.assertRaisesRegex(ValueError, 'original native'):
                measure.load_sealed_trace(p, hashlib.sha256(p.read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()
