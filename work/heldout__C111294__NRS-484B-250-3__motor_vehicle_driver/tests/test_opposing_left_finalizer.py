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

    def test_local_travel_subject_requires_opposite_original_actor(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            config_path = root / 'config.json'
            config = json.loads(config_path.read_text())
            config['cell_id'] = 'C111294'
            config['selected_case_id'] = ('heldout__C111294__NRS-484B-250-3__motor_vehicle_driver'
                                          '__opposing_left_travel_subject')
            config_path.write_text(json.dumps(config))
            context_path = root / 'opposing_left_context.json'
            context = json.loads(context_path.read_text())
            context['subject_role'] = 'opposite'
            context['subject_actor_id'] = context['opposite_actor_id']
            context_path.write_text(json.dumps(context))
            participant_rows = [json.loads(line) for line in
                                (root / 'opposing_left_participants.jsonl').read_text().splitlines()]
            trace_rows = [json.loads(line) for line in (root / 'trace.jsonl').read_text().splitlines()]
            for motion, participant in zip(trace_rows, participant_rows):
                motion['position_m'] = [sum(point[axis] for point in participant['opposite_corners']) / 4
                                        for axis in (0, 1)]
                motion['heading_deg'] = participant['opposite_heading_rad'] * 180 / 3.141592653589793
            (root / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in trace_rows))
            report = analyze(root)
            self.assertEqual(report['case_id'], config['selected_case_id'])
            self.assertIn('observed_opposite_heading_change_rad',
                          report['measurements']['opposing_left_observation']['value'])
            result = build_result(root, report)
            self.assertFalse(result['legal_acceptance_claimed'])
            trace_rows[0]['position_m'][0] += 10
            (root / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in trace_rows))
            with self.assertRaisesRegex(ValueError, 'body differs from trace'):
                analyze(root)
            trace_rows[0]['position_m'][0] -= 10
            (root / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in trace_rows))
            context['opposite_route'][-1]['heading_xy'] = [0, 1]
            context_path.write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, 'route turns'):
                analyze(root)
            context['opposite_route'][-1]['heading_xy'] = [-1, 0]
            context['subject_actor_id'] = context['turning_actor_id']
            context_path.write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, 'subject role differs'):
                analyze(root)


if __name__ == '__main__':
    unittest.main()
