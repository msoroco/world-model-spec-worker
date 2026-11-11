import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from headlamp_finalizer import analyze, build_result
from test_headlamp_follow_measurement import row


CASE = 'heldout__C178038__NRS-484D-215-2__motor_vehicle_driver__night_299_other'


def sources(root):
    (root / 'config.json').write_text(json.dumps({
        'selected_case_id': CASE, 'law_id': 'NRS-484D-215-2',
        'cell_id': 'C178038', 'actor': 'motor_vehicle_driver',
        'target_gap_ft': 299,
        'case': {'recording_description': {'channels': [], 'context_inputs': [],
                                           'limitations': ['CPU fixture only']}}}))
    (root / 'video_frames.jsonl').write_text(''.join(json.dumps({
        'video_frame': i, 'carla_frame': i, 'time_s': i * .05}) + '\n'
        for i in range(2)))
    (root / 'trace.jsonl').write_text(''.join(json.dumps({
        'frame': i, 'time_s': i * .05}) + '\n'
        for i in range(2)))
    (root / 'following_footprints.jsonl').write_text(''.join(json.dumps(row(i, 299)) + '\n'
                                                        for i in range(2)))
    (root / 'headlamp_readbacks.jsonl').write_text(''.join(json.dumps({
        'frame': i, 'time_s': i * .05, 'uppermost_distribution': False,
        'low_beam_readback': True}) + '\n' for i in range(2)))
    (root / 'lighting_context.json').write_text(json.dumps({
        'lighting_time_applies': True, 'time_source': 'cited clock premise'}))


class SavedHeadlampTests(unittest.TestCase):
    def test_original_join_and_canonical_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources(root)
            report = analyze(root)
            native = build_result(root, report)
            sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'runtime' / 'scenario_pipeline'))
            from worker_exchange.native_output import validate_result
            validate_result(native)
            self.assertFalse(native['physical_acceptance_claimed'])
            self.assertTrue((root / 'headlamp_gap_ft.jsonl').is_file())
            (root / 'headlamp_readbacks.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                analyze(root)

    def test_stale_trace_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources(root)
            trace = root / 'trace.jsonl'
            rows = [json.loads(line) for line in trace.read_text().splitlines()]
            rows[1]['frame'] = 17
            trace.write_text(''.join(json.dumps(item) + '\n' for item in rows))
            with self.assertRaisesRegex(ValueError, 'join failed'):
                analyze(root)


if __name__ == '__main__':
    unittest.main()
