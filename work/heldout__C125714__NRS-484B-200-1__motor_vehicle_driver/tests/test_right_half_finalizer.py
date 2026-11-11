import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from right_half_finalizer import analyze, build_result
from test_right_half_measurement import row


CASE = 'heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__baseline_right_east'


class FinalizerTests(unittest.TestCase):
    def sources(self, root):
        (root / 'config.json').write_text(json.dumps({
            'selected_case_id': CASE, 'law_id': 'NRS-484B-200-1',
            'cell_id': 'C125714', 'actor': 'motor_vehicle_driver',
            'case': {'recording_description': {'channels': [], 'context_inputs': [],
                                               'limitations': ['CPU fixture only']}}}))
        (root / 'video_frames.jsonl').write_text(''.join(json.dumps({
            'video_frame': index, 'carla_frame': index, 'time_s': index * .05}) + '\n'
            for index in range(2)))
        (root / 'trace.jsonl').write_text(''.join(json.dumps({
            'frame': index, 'time_s': index * .05}) + '\n'
            for index in range(2)))
        (root / 'directed_roadway_footprints.jsonl').write_text(''.join(
            json.dumps(row(index, 1, [0.2, 0.2, 1.8, 1.8])) + '\n'
            for index in range(2)))

    def test_join_and_missing_original_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.sources(root)
            report = analyze(root)
            self.assertEqual(report['case_id'], CASE)
            self.assertEqual(report['measurements']['right_half_occupancy']['value']['frames_entirely_right'], [0, 1])
            self.assertFalse(report['legal_acceptance_claimed'])
            native = build_result(root, report)
            sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'runtime' / 'scenario_pipeline'))
            from worker_exchange.native_output import validate_result
            validate_result(native)
            self.assertFalse(native['setup_confirmed'])
            self.assertTrue((root / 'right_half_offset_m.jsonl').is_file())
            (root / 'directed_roadway_footprints.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                analyze(root)

    def test_stale_frame_join_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.sources(root)
            trace = root / 'trace.jsonl'
            rows = [json.loads(line) for line in trace.read_text().splitlines()]
            rows[1]['frame'] = 9
            trace.write_text(''.join(json.dumps(item) + '\n' for item in rows))
            with self.assertRaisesRegex(ValueError, 'join failed'):
                analyze(root)

    def test_other_exception_case_keeps_legal_judgment_open(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.sources(root)
            config_path = root / 'config.json'
            config = json.loads(config_path.read_text())
            config['selected_case_id'] = CASE.replace('baseline_right_east', 'right_half_closed')
            config_path.write_text(json.dumps(config))
            report = analyze(root)
            self.assertIsNone(report['measurements']['right_half_occupancy']['value']['exception_legal_judgment'])


if __name__ == '__main__':
    unittest.main()
