import json
from pathlib import Path
import unittest

folder = Path(__file__).resolve().parents[1]

class CandidateTests(unittest.TestCase):
    def test_three_distinct_changes_hold_capture_and_case(self):
        primary = json.loads((folder / 'construction.json').read_text())
        files = {item['path']: item['content'] for item in primary['files']}
        variants = [json.loads((folder / 'cases' / f'fallback{i}-construction.json').read_text())
                    for i in (1, 2, 3)]
        for candidate in variants:
            self.assertEqual(candidate['case_id'], primary['case_id'])
            self.assertEqual(candidate['recording_description'], primary['recording_description'])
            self.assertEqual(next(item['content'] for item in candidate['files']
                                  if item['path'] == 'config.json'), files['config.json'])
        changed = []
        for candidate in variants:
            source = {item['path']: item['content'] for item in candidate['files']}
            changed.append({name for name in files if source[name] != files[name]})
        self.assertEqual(changed, [{'runner.py'}, {'runner.py'}, {'fire_camera_capture.py'}])
        self.assertIn('step_m=2.5', next(item['content'] for item in variants[0]['files']
                                       if item['path'] == 'runner.py'))
        self.assertIn('gain=0.12, speed_gain=0.22', next(item['content'] for item in variants[1]['files']
                                                       if item['path'] == 'runner.py'))
        self.assertIn('(1.8, 0.0, 2.3)', next(item['content'] for item in variants[2]['files']
                                            if item['path'] == 'fire_camera_capture.py'))

if __name__ == '__main__': unittest.main()
