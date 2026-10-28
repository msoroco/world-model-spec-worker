import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner import capture_frame, cleanup_action
from analyze import assess, target_matched
from worker_exchange.native_output import FrameMap


class SpeedPackageTests(unittest.TestCase):
    def test_adjacent_speed_probe_windows_are_disjoint(self):
        targets = [mph * .44704 for mph in (79, 80, 81)]
        for observed in targets:
            self.assertEqual(sum(target_matched(observed, target) for target in targets), 1)

    def test_capture_writer_records_original_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'video_frames.jsonl'
            with FrameMap(path) as writer:
                capture_frame(writer, 21714, .05, {'view0': {'width': 1920}})
                capture_frame(writer, 21715, .10, {'view0': {'width': 1920}})
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([(r['video_frame'], r['carla_frame'], r['native_frame'])
                              for r in rows], [(0, 21714, 21714), (1, 21715, 21715)])

    def test_cleanup_failure_keeps_later_actions(self):
        calls = []
        errors = []
        cleanup_action(errors, 'sensor', lambda: (_ for _ in ()).throw(RuntimeError('failed')))
        cleanup_action(errors, 'world restore', lambda: calls.append('restore'))
        self.assertEqual(calls, ['restore'])
        self.assertIn('sensor', errors[0])

    def test_missing_original_capture_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                assess(directory)


if __name__ == '__main__':
    unittest.main()
