"""Selected separated-entry source and proof contract."""
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
CASE = HERE.name+'__off_ego_left_separated'


class SeparatedCase(unittest.TestCase):
    def test_continuous_source_matches_release_and_complete_body_timing(self):
        manifest = json.loads((HERE/'execution-manifest.json').read_text())
        entry = next(row for row in manifest['cases'] if row['case_id'] == CASE)
        construction = json.loads((HERE/entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        self.assertEqual((config['ego_release_frame'], config['other_release_frame']), (20, 60))
        diagnostic = json.loads((HERE/'cases/off_ego_left_separated/diagnostic.json').read_text())
        frames = [json.loads(row) for row in diagnostic['files']['video_frames.jsonl'].splitlines()]
        controls = [json.loads(row) for row in diagnostic['files']['controller_history.jsonl'].splitlines()]
        self.assertEqual(len(frames), 97)
        self.assertEqual([row['carla_frame'] for row in frames], list(range(100, 197)))
        self.assertEqual([row['video_frame'] for row in frames], list(range(97)))
        self.assertEqual([row['frame'] for row in controls if row['ego_held']], list(range(100, 120)))
        self.assertEqual([row['frame'] for row in controls if row['other_held']], list(range(100, 160)))
        receipt = json.loads((HERE/entry['compatibility']['receipt']).read_text())
        timing = receipt['measurement_examples']['entry_timing']['value']
        self.assertEqual(timing['first_complete_body_entry']['ego']['frame'], 164)
        self.assertEqual(timing['first_complete_body_entry']['other']['frame'], 192)
        self.assertAlmostEqual(timing['absolute_difference_s'], 1.4)
        self.assertEqual(timing['approximately_same_time_judgment'], 'unresolved')
