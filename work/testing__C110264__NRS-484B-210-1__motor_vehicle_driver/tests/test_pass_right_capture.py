import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pass_right_capture import collect_native_trace
from pass_right_measure import observe
from test_pass_right_measure import trace


class FakeFrameMap:
    def __init__(self):
        self.calls = []

    def append(self, frame, time_s, **extra):
        self.calls.append((frame, time_s, extra))


def rows(mode='signal', count=900):
    seed = trace(mode)['frames']
    out = []
    for i in range(count):
        base = copy.deepcopy(seed[min(i, 11)])
        if i > 11:
            base['ego_s_m'] += (i - 11) * 0.7
            base['target_s_m'] += (i - 11) * 0.15
        base.update(native_frame_id=1420 + i, elapsed_seconds=72.5 + i / 20,
                    ego_id=10, target_id=11,
                    camera_frame_ids={name: 1420 + i for name in
                                      ('front', 'rear', 'left', 'right')})
        out.append(base)
    return out


def road():
    return {'source_kind': 'original_native_map_geometry',
            'public_highway_observed': True, 'two_way_observed': True,
            'intersection_s_m': [55, 70], 'actor_half_width_m': 0.9}


class TestNativeCaptureJoin(unittest.TestCase):
    def test_complete_source_rows_and_frame_map(self):
        frame_map = FakeFrameMap()
        native = collect_native_trace(rows(), road(), 10, 11, frame_map)
        self.assertEqual(len(native['frames']), 900)
        self.assertEqual(len(frame_map.calls), 900)
        self.assertEqual(frame_map.calls[0][0], 1420)
        self.assertEqual(frame_map.calls[-1][2]['original_index'], 899)
        self.assertTrue(observe(native)['target_left_signal_during_pass'])
        self.assertFalse(native['physical_acceptance_claimed'])

    def test_rejects_clock_and_camera_gaps(self):
        samples = rows(count=12); samples[4]['native_frame_id'] += 1
        with self.assertRaisesRegex(ValueError, 'Native frame identity'):
            collect_native_trace(samples, road(), 10, 11, FakeFrameMap(), 12)
        samples = rows(count=12); samples[4]['camera_frame_ids']['front'] += 1
        frame_map = FakeFrameMap()
        with self.assertRaisesRegex(ValueError, 'camera frame does not join'):
            collect_native_trace(samples, road(), 10, 11, frame_map, 12)
        self.assertEqual(frame_map.calls, [])
        samples = rows(count=12); samples[4]['elapsed_seconds'] += 0.01
        with self.assertRaisesRegex(ValueError, 'Native 20 Hz clock'):
            collect_native_trace(samples, road(), 10, 11, FakeFrameMap(), 12)

    def test_rejects_actor_and_context_drift(self):
        samples = rows(count=12); samples[1]['target_id'] = 99
        with self.assertRaisesRegex(ValueError, 'actor identity drift'):
            collect_native_trace(samples, road(), 10, 11, FakeFrameMap(), 12)
        context = road(); context['source_kind'] = 'requested_map'
        with self.assertRaisesRegex(ValueError, 'source-reviewed road'):
            collect_native_trace(rows(count=12), context, 10, 11, FakeFrameMap(), 12)
        samples = rows(count=12); samples[2]['target_left_signal'] = 1
        with self.assertRaisesRegex(ValueError, 'left signal must be boolean'):
            collect_native_trace(samples, road(), 10, 11, FakeFrameMap(), 12)


if __name__ == '__main__':
    unittest.main()
