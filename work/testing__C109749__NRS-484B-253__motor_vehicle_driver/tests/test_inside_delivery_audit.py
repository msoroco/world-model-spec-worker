import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from inside_delivery_audit import validate_inside_sequence


class InsideDeliverySequenceTests(unittest.TestCase):
    def fixture(self, root, name):
        files = json.loads((ROOT / 'cases' / name / 'diagnostic.json').read_text())['files']
        for source in ('intersection_geometry.json', 'interaction_history.jsonl'):
            (root / source).write_text(files[source])
        return [json.loads(line) for line in files['interaction_history.jsonl'].splitlines()]

    def test_yield_sequence_and_saved_measurement_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, 'inside_yield')
            result = {'measured_values': {'initial_oncoming_clearance_frame': 38036,
                                          'ego_turn_start_frame': 38037,
                                          'subject_yield_frames': [38035]}}
            self.assertEqual(validate_inside_sequence(root, 'yield', result)['subject_yield_frames'], [38035])
            result['measured_values']['ego_turn_start_frame'] = 38035
            with self.assertRaisesRegex(ValueError, 'Saved measurement differs'):
                validate_inside_sequence(root, 'yield', result)

    def test_proceed_sequence_rejects_stopped_subject(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = self.fixture(root, 'inside_no_yield')
            result = {'measured_values': {'initial_oncoming_clearance_frame': 38036,
                                          'ego_turn_start_frame': 38035,
                                          'moving_overlap_frames': [38035]}}
            self.assertEqual(validate_inside_sequence(root, 'proceed', result)['moving_overlap_frames'], [38035])
            rows[2]['ego']['velocity_xy_mps'] = [0, 0]
            (root / 'interaction_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'Original moving turn'):
                validate_inside_sequence(root, 'proceed', result)
