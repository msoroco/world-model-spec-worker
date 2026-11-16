import hashlib
import json
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]


class FourthCaseTests(unittest.TestCase):
    def test_opposite_approach_intention_and_three_fallbacks(self):
        manifest = json.loads((HERE / 'execution-manifest.json').read_text())
        fourth = next(c for c in manifest['cases']
                      if c['case_id'].endswith('__stop_opposite_left_turn'))
        self.assertEqual([c['changed_knobs'] for c in fourth['candidates']],
                         [['site.approaches.other.route_xy_m'], ['other_release_frame'],
                          ['site.camera_poses.reference_corner']])
        for candidate in [fourth, *fourth['candidates']]:
            construction = HERE / candidate['construction']
            self.assertEqual(hashlib.sha256(construction.read_bytes()).hexdigest(),
                             candidate['construction_sha256'])
            files = {f['path']: f['content']
                     for f in json.loads(construction.read_text())['files']}
            site = json.loads(files['site.json'])
            self.assertEqual(site['approach_relation'], 'opposite_directions')
            self.assertTrue(site['other_left_turn_intended'])
            self.assertEqual(site['approaches']['ego']['highway_id'],
                             site['approaches']['other']['highway_id'])
            receipt = json.loads((HERE / candidate['compatibility']['receipt']).read_text())
            self.assertTrue(receipt['passed'])
            self.assertTrue(receipt['measurement_examples']['relative_right_side']
                            ['value']['inapplicable_to_opposite_exception'])
            self.assertTrue(receipt['measurement_examples']['opposite_left_turn_context']
                            ['value']['opposite_approach'])
            self.assertEqual(receipt['measurement_examples']['opposite_left_turn_context']
                             ['value']['exception_judgment'], 'unresolved')
            self.assertEqual(receipt['negative_removed'], 'controller_history.jsonl')


if __name__ == '__main__':
    unittest.main()
