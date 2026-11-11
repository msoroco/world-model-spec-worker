import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from endangerment_finalizer import analyze, build_result, assess_exposure_passage
from test_endangerment_measurement import sample, square


CASE = 'heldout__C136539__NRS-484B-600-1b__motor_vehicle_driver__moderate_person_exposure'


def sources(root):
    (root / 'config.json').write_text(json.dumps({
        'selected_case_id': CASE, 'law_id': 'NRS-484B-600-1b',
        'cell_id': 'C136539', 'actor': 'motor_vehicle_driver',
        'case': {'recording_description': {'channels': [], 'context_inputs': [],
                                           'limitations': ['CPU fixture only']}}}))
    (root / 'video_frames.jsonl').write_text(''.join(json.dumps({
        'video_frame': index, 'carla_frame': index, 'time_s': index * .05}) + '\n'
        for index in range(2)))
    (root / 'trace.jsonl').write_text(''.join(json.dumps({
        'frame': index, 'time_s': index * .05}) + '\n'
        for index in range(2)))
    (root / 'exposed_actor_footprints.jsonl').write_text(''.join(
        json.dumps(sample(index, 3)) + '\n' for index in range(2)))


class FinalizerTests(unittest.TestCase):
    def test_physical_passage_requires_original_before_and_after_body(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources(root)
            path = root / 'exposed_actor_footprints.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[-1]['ego_corners_xy'] = square(5)
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            self.assertEqual(assess_exposure_passage(root)['status'], 'met')
            rows[-1]['ego_corners_xy'] = square(1)
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            self.assertEqual(assess_exposure_passage(root)['status'], 'not_met')

    def test_saved_join_and_missing_source_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources(root)
            result = analyze(root)
            self.assertEqual(result['case_id'], CASE)
            self.assertAlmostEqual(result['measurements']['person_or_property_exposure']['value']['minimum_surface_gap_m'], 2)
            self.assertFalse(result['legal_acceptance_claimed'])
            native = build_result(root, result)
            sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'runtime' / 'scenario_pipeline'))
            from worker_exchange.native_output import validate_result
            validate_result(native)
            self.assertFalse(native['setup_confirmed'])
            self.assertFalse(native['physical_acceptance_claimed'])
            self.assertTrue((root / 'exposure_gap_m.jsonl').is_file())
            (root / 'exposed_actor_footprints.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                analyze(root)

    def test_stale_trace_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources(root)
            path = root / 'trace.jsonl'
            values = [json.loads(line) for line in path.read_text().splitlines()]
            values[1]['time_s'] = .1
            path.write_text(''.join(json.dumps(value) + '\n' for value in values))
            with self.assertRaisesRegex(ValueError, 'join failed'):
                analyze(root)


if __name__ == '__main__':
    unittest.main()
