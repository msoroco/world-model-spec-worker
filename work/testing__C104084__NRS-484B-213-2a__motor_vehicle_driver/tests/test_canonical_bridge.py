import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parents[1] / 'runtime'))
sys.path.insert(0, str(ROOT.parents[1] / 'runtime' / 'scenario_pipeline'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_bridge import bridge
from test_saved_delivery import ASSIGNMENT, CASE, video_attempt


class CanonicalBridgeTests(unittest.TestCase):
    DESCRIPTION = {'channels': [{'name': 'ego_center_offset_m', 'unit': 'm',
        'method': 'original saved body corners', 'time_window': 'all frames',
        'reference_frame': 'reviewed road center', 'uncertainty': 'unreviewed',
        'sampling_rate_hz': 20}], 'context_inputs': [], 'limitations': []}

    def prepared(self, root):
        original = root / 'original'
        original.mkdir()
        video_attempt(original)
        (root / 'config.json').write_text(json.dumps({'case': {'recording_description':
            self.DESCRIPTION}}) + '\n')
        (root / 'runner.py').write_text('pass\n')
        (root / 'construction.json').write_text('{}\n')
        (root / 'road.xodr').write_text('original road\n')
        (root / 'trace.jsonl').write_text(''.join(json.dumps({'frame': frame,
            'time_s': frame / 20, 'position': {'x': frame, 'y': 0, 'z': 0},
            'heading_deg': 0, 'speed_mps': 1}) + '\n' for frame in range(3)))
        native = root / 'capture' / 'native'
        native.mkdir(parents=True)
        (root / 'capture' / 'manifest.json').write_text(json.dumps({'frames': 3}) + '\n')
        (native / 'frames.jsonl').write_text(''.join(json.dumps({'frame': frame}) + '\n'
                                                    for frame in range(3)))
        (root / 'capture' / 'evidence.jsonl').write_text(''.join(json.dumps({
            'original_frame': frame, 'replay_frame': frame,
            'recording_time_s': frame / 20}) + '\n' for frame in range(3)))
        return original

    def test_original_graph_and_body_join_publishes_sealed_capture(self):
        scratch = ROOT.parents[1] / '.runtime-work' / 'c104084-bridge-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            root = Path(folder)
            original = self.prepared(root)
            result = bridge(root, original, assignment_id=ASSIGNMENT, case_id=CASE,
                            release={'world_restored': True, 'actors_released': True,
                                     'sensors_released': True, 'errors': []},
                            expected_frames=3)
            self.assertEqual(result['frame_count'], 3)
            self.assertTrue((root / 'capture-seal.json').is_file())
            self.assertEqual(len((root / 'crest-derived-trace.jsonl').read_text().splitlines()), 3)
            self.assertEqual(len((root / 'trace.jsonl').read_text().splitlines()), 3)
            self.assertTrue((root / 'overview.mkv').is_file())

    def test_pinned_native_validation_accepts_source_shaped_rows_and_rejects_drift(self):
        from batch_pipeline.carla import validate_attempt
        scratch = ROOT.parents[1] / '.runtime-work' / 'c104084-bridge-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            root = Path(folder)
            original = self.prepared(root)
            bridge(root, original, assignment_id=ASSIGNMENT, case_id=CASE,
                   release={'world_restored': True, 'actors_released': True,
                            'sensors_released': True, 'errors': []}, expected_frames=3)
            request = {'case': {'case_id': CASE, 'variable_assignments': {},
                                'sweep_measurements': []},
                       'cell': {'cell_id': 'C104084'}, 'actor': 'motor_vehicle_driver'}
            construction = {'recording_description': self.DESCRIPTION}
            validated = validate_attempt(root, request, construction,
                                         {'recorded_exit_code': 0}, {})
            self.assertEqual(len(validated['video_validation']), 4)
            mapping = root / 'video_frames.jsonl'
            rows = [json.loads(line) for line in mapping.read_text().splitlines()]
            rows[1]['carla_frame'] = 99
            mapping.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'Video/trace frame mismatch'):
                validate_attempt(root, request, construction,
                                 {'recorded_exit_code': 0}, {})

    def test_changed_graph_frame_rejected_before_publication(self):
        scratch = ROOT.parents[1] / '.runtime-work' / 'c104084-bridge-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            root = Path(folder)
            original = self.prepared(root)
            (root / 'capture' / 'native' / 'frames.jsonl').write_text(''.join(
                json.dumps({'frame': frame}) + '\n' for frame in (0, 99, 2)))
            with self.assertRaisesRegex(ValueError, 'graph/body/ray frame join'):
                bridge(root, original, assignment_id=ASSIGNMENT, case_id=CASE,
                       release={'world_restored': True, 'actors_released': True,
                                'sensors_released': True, 'errors': []}, expected_frames=3)
            self.assertFalse((root / 'capture-seal.json').exists())


if __name__ == '__main__':
    unittest.main()
