"""Guard the current source camera names in every selected construction."""
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1]


class CurrentCameraProfileTest(unittest.TestCase):
    def test_selected_camera_source_matches_current_config(self):
        manifest = json.loads((HERE / 'execution-manifest.json').read_text())
        expected = ['overview', 'approach', 'reference_corner', 'driver_reference']
        canonical = (HERE / 'cameras.py').read_text()
        for entry in manifest['cases']:
            for candidate in [entry, *entry['candidates']]:
                with self.subTest(case=entry['case_id'], candidate=candidate.get('id', 'primary')):
                    bundle = json.loads((HERE / candidate['construction']).read_text())
                    files = {item['path']: item['content'] for item in bundle['files']}
                    self.assertEqual(files['cameras.py'], canonical)
                    config = json.loads(files['config.json'])
                    self.assertEqual([camera['name'] for camera in config['cameras']], expected)
                    scope = {}
                    exec(compile(files['cameras.py'], 'cameras.py', 'exec'), scope)
                    requested = scope['camera_plan'](config['candidate_id'])
                    self.assertEqual([camera['name'] for camera in requested], expected)
                    self.assertEqual(requested[0]['fov_deg'],
                                     105 if config['candidate_id'] == 'fallback3' else 90)


if __name__ == '__main__':
    unittest.main()
