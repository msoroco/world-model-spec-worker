import hashlib
import json
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]


class SecondCaseTests(unittest.TestCase):
    def test_exact_ego_right_primary_and_distinct_fallbacks(self):
        manifest = json.loads((HERE / 'execution-manifest.json').read_text())
        case = next(c for c in manifest['cases']
                    if c['case_id'].endswith('__stop_ego_right_near_time'))
        self.assertEqual([c['id'] for c in case['candidates']],
                         ['fallback1', 'fallback2', 'fallback3'])
        self.assertEqual([c['changed_knobs'] for c in case['candidates']],
                         [['other_release_frame'], ['site.camera_poses.overview'],
                          ['capture_duration']])
        for candidate in [case, *case['candidates']]:
            construction = HERE / candidate['construction']
            self.assertEqual(hashlib.sha256(construction.read_bytes()).hexdigest(),
                             candidate['construction_sha256'])
            content = json.loads(construction.read_text())
            self.assertEqual(content['case_id'], case['case_id'])
            files = {f['path']: f['content'] for f in content['files']}
            config = json.loads(files['config.json'])
            site = json.loads(files['site.json'])
            self.assertEqual(config['selected_case_id'], case['case_id'])
            self.assertEqual(site['approaches']['other']['forward_xy'], [0, -1])
            self.assertEqual(site['approaches']['other']['route_xy_m'],
                             [[15, 15], [15, 0], [15, -15]])
            self.assertEqual(hashlib.sha256(files['site.json'].encode()).hexdigest(),
                             config['site_packet']['sha256'])
            receipt = json.loads((HERE / candidate['compatibility']['receipt']).read_text())
            self.assertTrue(receipt['passed'])
            self.assertEqual(receipt['candidate_id'], candidate.get('id', 'primary'))
            self.assertFalse(receipt['measurement_examples']['relative_right_side']
                             ['value']['other_spatially_right'])


if __name__ == '__main__':
    unittest.main()
