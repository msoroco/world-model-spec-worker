import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CASES=('primary','right','separated','opposite')


def files(construction):
    return {row['path']:row['content'] for row in construction['files']}


class FallbackConstructionTests(unittest.TestCase):
    def test_distinct_physical_adjustments_preserve_case_variables(self):
        for prefix in CASES:
            with self.subTest(case=prefix):
                manifest=json.loads((ROOT/(prefix+'-candidate-manifest.json')).read_text())
                entry=manifest['cases'][0]
                primary=json.loads((ROOT/entry['construction']).read_text())
                original=files(primary)
                config=json.loads(original['config.json'])
                site=json.loads(original['site.json'])
                self.assertEqual([c['id'] for c in entry['candidates']],
                                 ['fallback1','fallback2','fallback3'])
                for candidate in entry['candidates']:
                    altered=json.loads((ROOT/candidate['construction']).read_text())
                    changed=files(altered)
                    cfg=json.loads(changed['config.json'])
                    scene=json.loads(changed['site.json'])
                    self.assertEqual(altered['case_id'],primary['case_id'])
                    self.assertEqual(cfg['other_release_frame'],config['other_release_frame'])
                    self.assertEqual(scene['approach_relation'],site['approach_relation'])
                    self.assertEqual(scene['crossing_polygon_xy_m'],site['crossing_polygon_xy_m'])
                    self.assertEqual({k:v['forward_xy'] for k,v in scene['approaches'].items()},
                                     {k:v['forward_xy'] for k,v in site['approaches'].items()})
                    if candidate['id']=='fallback1':
                        self.assertNotEqual(scene['approaches']['ego']['spawn_pose'],
                                            site['approaches']['ego']['spawn_pose'])
                        self.assertEqual(scene['approaches']['other']['spawn_pose'],
                                         site['approaches']['other']['spawn_pose'])
                    elif candidate['id']=='fallback2':
                        self.assertEqual(scene['approaches']['ego']['spawn_pose'],
                                         site['approaches']['ego']['spawn_pose'])
                        self.assertNotEqual(scene['approaches']['other']['spawn_pose'],
                                            site['approaches']['other']['spawn_pose'])
                    else:
                        self.assertNotEqual(scene['camera_poses']['overview'],
                                            site['camera_poses']['overview'])
                        self.assertEqual(scene['approaches'],site['approaches'])


if __name__=='__main__':unittest.main()
