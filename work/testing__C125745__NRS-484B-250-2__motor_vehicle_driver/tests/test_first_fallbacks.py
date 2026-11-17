import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from build_first_fallbacks import build_timing_sweep_point


class FirstFallbackTests(unittest.TestCase):
    def test_48_frame_timing_sweep_point_preserves_exact_primary(self):
        primary = json.loads((HERE / 'construction.json').read_text())
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'sweep48'
            manifest = build_timing_sweep_point(output)
            construction = json.loads((output / 'construction.json').read_text())
            config = json.loads((output / 'config.json').read_text())
            baseline = json.loads((HERE / 'config.json').read_text())
            self.assertEqual(config.pop('other_release_frame'), 48)
            baseline.pop('other_release_frame')
            self.assertEqual(config, baseline)
            self.assertEqual(construction['sweep_point']['sweep_id'], 'c125745-1')
            self.assertEqual(construction['case_id'], primary['case_id'])
            self.assertEqual({item['path'] for item in construction['files']},
                             {item['path'] for item in primary['files']})
            self.assertEqual(json.loads(next(item['content'] for item in construction['files']
                                             if item['path'] == 'config.json'))['other_release_frame'], 48)
            self.assertEqual(manifest['cases'][0]['construction_sha256'],
                             hashlib.sha256((output / 'construction.json').read_bytes()).hexdigest())

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
