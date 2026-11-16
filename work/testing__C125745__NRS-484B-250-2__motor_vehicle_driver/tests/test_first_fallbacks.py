import hashlib
import json
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]


class FirstFallbackTests(unittest.TestCase):
    def test_three_distinct_exact_constructions(self):
        manifest = json.loads((HERE / 'execution-manifest.json').read_text())
        case = manifest['cases'][0]
        self.assertEqual([c['id'] for c in case['candidates']],
                         ['fallback1', 'fallback2', 'fallback3'])
        self.assertEqual([c['changed_knobs'] for c in case['candidates']],
                         [['other_release_frame'], ['site.camera_poses.overview'],
                          ['capture_duration']])
        configs = []
        sites = []
        for candidate in case['candidates']:
            path = HERE / candidate['construction']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                             candidate['construction_sha256'])
            construction = json.loads(path.read_text())
            self.assertEqual(construction['case_id'], case['case_id'])
            files = {f['path']: f['content'] for f in construction['files']}
            configs.append(json.loads(files['config.json']))
            sites.append(json.loads(files['site.json']))
            self.assertEqual(hashlib.sha256(files['site.json'].encode()).hexdigest(),
                             configs[-1]['site_packet']['sha256'])
            self.assertEqual(construction['fallback_design']['changed_knob'],
                             candidate['changed_knobs'][0])
        self.assertEqual(configs[0]['other_release_frame'], 32)
        self.assertEqual(sites[1]['camera_poses']['overview'], [28, -22, 12, 135, -20, 0])
        self.assertEqual((configs[2]['frames'], configs[2]['duration_s']), (1100, 55))
        self.assertEqual(len({c['construction_sha256'] for c in case['candidates']}), 3)


if __name__ == '__main__':
    unittest.main()
