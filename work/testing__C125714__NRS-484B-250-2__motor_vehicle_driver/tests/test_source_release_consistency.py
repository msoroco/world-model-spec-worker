import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASE_DIRS = (ROOT,
             ROOT / 'cases/source_verified_other_left_near_time',
             ROOT / 'cases/source_verified_other_right_earlier',
             ROOT / 'cases/source_verified_other_right_later')


class SourceReleaseConsistencyTests(unittest.TestCase):
    def test_other_body_does_not_move_before_release(self):
        for folder in CASE_DIRS:
            with self.subTest(case=folder.name):
                construction = json.loads((folder / 'construction.json').read_text())
                files = {item['path']: item['content'] for item in construction['files']}
                config = json.loads(files['config.json'])
                diagnostic = json.loads((folder / 'diagnostic.json').read_text())
                history = [json.loads(line) for line in
                           diagnostic['files']['crossing_history.jsonl'].splitlines()]
                controls = [json.loads(line) for line in
                            diagnostic['files']['controller_history.jsonl'].splitlines()]
                release = config['other_release_frame']
                origin = history[0]['other']['position_xy_m']
                self.assertTrue(all(row['other']['position_xy_m'] == origin
                                    for row in history[:release + 1]))
                self.assertNotEqual(history[release + 1]['other']['position_xy_m'], origin)
                self.assertFalse(any(row['other_entered_once'] for row in controls[:release + 1]))
                self.assertTrue(any(row['other_entered_once'] for row in controls[release + 1:]))
                self.assertFalse(controls[-1]['other_inside_before_tick'])


if __name__ == '__main__':
    unittest.main()
