import json
from pathlib import Path
import sys
import tempfile
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from alley_finalizer import analyze, assess_passage, build_result
from worker_exchange.native_output import validate_result


def box(x, y):
    return [[x-.2, y-.2], [x+.2, y-.2],
            [x+.2, y+.2], [x-.2, y+.2]]


def rows(path, values):
    path.write_text(''.join(json.dumps(value) + '\n' for value in values))


class SavedOriginalSourceTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = {'law_id': 'NRS-484B-600-1b', 'cell_id': 'C10364',
            'actor': 'motor_vehicle_driver',
            'selected_case_id': 'heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver__person_3mps',
            'case': {'recording_description': {'channels': []}}}
        (self.root / 'config.json').write_text(json.dumps(self.config))
        self.frames = [{'frame': 10+i, 'time_s': i*.05,
            'ego_id': 1, 'pedestrian_id': 2, 'property_id': 3,
            'ego_corners': box(i*.5, 0),
            'pedestrian_corners': box(1, 1),
            'property_corners': box(1.5, -1)} for i in range(5)]
        rows(self.root / 'participant_footprints.jsonl', self.frames)
        rows(self.root / 'ego_motion.jsonl', [
            {'frame': x['frame'], 'time_s': x['time_s'], 'ego_id': 1,
             'velocity_xy': [10, 0], 'acceleration_xy': [-2, 0],
             'forward_xy': [1, 0]} for x in self.frames])
        rows(self.root / 'trace.jsonl', [
            {'frame': x['frame'], 'time_s': x['time_s']} for x in self.frames])
        rows(self.root / 'video_frames.jsonl', [
            {'video_frame': i, 'carla_frame': x['frame'], 'time_s': x['time_s']}
            for i, x in enumerate(self.frames)])

    def test_originals_yield_both_interests_without_verdict(self):
        report = analyze(self.root)
        value = report['measurements']['alley_original_exposure']['value']
        self.assertEqual(value['frame_count'], 5)
        self.assertGreater(value['minimum_pedestrian_gap_m'], 0)
        self.assertGreater(value['minimum_property_gap_m'], 0)
        self.assertFalse(report['physical_acceptance_claimed'])
        self.assertFalse(report['legal_acceptance_claimed'])
        passage = assess_passage(self.root)
        self.assertEqual(passage['status'], 'met')
        self.assertTrue(passage['details']['pedestrian_passage_observed'])
        self.assertTrue(passage['details']['property_passage_observed'])
        result = build_result(self.root, report)
        validate_result(result)
        self.assertIn('pedestrian_gap_m', result['realized_observables'])
        self.assertIn('property_gap_m', result['realized_observables'])
        self.assertEqual(len(result['recording_evidence']), 3)
        self.assertFalse(result['physical_acceptance_claimed'])
        self.assertFalse(result['legal_acceptance_claimed'])

    def test_wrong_case_and_missing_original_rejected(self):
        self.config['selected_case_id'] = 'foreign__person_3mps'
        (self.root / 'config.json').write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError, 'identity'):
            analyze(self.root)
        self.config['selected_case_id'] = 'heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver__person_3mps'
        (self.root / 'config.json').write_text(json.dumps(self.config))
        (self.root / 'ego_motion.jsonl').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing required source'):
            analyze(self.root)


if __name__ == '__main__':
    unittest.main()
