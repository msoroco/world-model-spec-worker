import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ending_road_camera import CAMERAS
from opposing_left_finalizer import analyze, build_result
import test_opposing_left_source


class OpposingLeftFinalizerTest(unittest.TestCase):
    def fixture(self, root):
        test_opposing_left_source.OpposingSourceTests().fixture(root)
        config = {'selected_case_id': 'heldout__C293604__NRS-484B-250-3__motor_vehicle_driver__opposing_left_turn',
                  'law_id': 'NRS-484B-250-3', 'cell_id': 'C293604',
                  'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'frames': 160,
                  'cameras': [{'name': name, 'width': size[0], 'height': size[1]}
                              for name, (_, _, size, _) in CAMERAS.items()],
                  'case': {'recording_description': {'summary': 'opposing left software fixture'}}}
        (root / 'config.json').write_text(json.dumps(config))
        mapping = [json.loads(line) for line in (root / 'video_frames.jsonl').read_text().splitlines()]
        for index, row in enumerate(mapping):
            row['video_frame'] = index
        (root / 'video_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in mapping))
        (root / 'trace.jsonl').write_text(''.join(json.dumps({'frame': row['carla_frame'],
                'time_s': row['time_s']}) + '\n' for row in mapping))

    def test_source_bound_report_and_missing_trace_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            report = analyze(root)
            self.assertEqual(report['measurements']['opposing_left_observation']['method'], 'measure_opposing_left')
            self.assertIn('trace.jsonl', report['measurements']['opposing_left_observation']['sources'])
            result = build_result(root, report)
            self.assertFalse(result['maneuver_completed'])
            self.assertFalse(result['physical_acceptance_claimed'])
            (root / 'trace.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source: trace.jsonl'):
                analyze(root)

    def test_stale_frame_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            rows = [json.loads(line) for line in (root / 'trace.jsonl').read_text().splitlines()]
            rows[1]['frame'] = 999
            (root / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'frame-map join failed'):
                analyze(root)


if __name__ == '__main__':
    unittest.main()
