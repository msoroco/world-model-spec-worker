import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from build_third_fallbacks import build_yield_sweep_point


class ThirdCaseTests(unittest.TestCase):
    def test_16_frame_yield_hold_sweep_point_preserves_exact_case(self):
        primary = json.loads((HERE / 'third-construction.json').read_text())
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'yield16'
            manifest = build_yield_sweep_point(output)
            construction = json.loads((output / 'construction.json').read_text())
            config = json.loads((output / 'config.json').read_text())
            baseline = json.loads((HERE / 'third-config.json').read_text())
            self.assertEqual(config.pop('ego_hold_after_clear_frames'), 16)
            baseline.pop('ego_hold_after_clear_frames')
            self.assertEqual(config, baseline)
            self.assertEqual(construction['sweep_point']['sweep_id'], 'c125745-2')
            self.assertEqual(construction['case_id'], primary['case_id'])
            self.assertEqual({item['path'] for item in construction['files']},
                             {item['path'] for item in primary['files']})
            self.assertEqual(json.loads(next(item['content'] for item in construction['files']
                                             if item['path'] == 'config.json'))['ego_hold_after_clear_frames'], 16)
            self.assertEqual(manifest['cases'][0]['construction_sha256'],
                             hashlib.sha256((output / 'construction.json').read_bytes()).hexdigest())

    def test_separated_original_entry_measurement_and_hold_construction(self):
        manifest = json.loads((HERE / 'execution-manifest.json').read_text())
        third = next(c for c in manifest['cases']
                     if c['case_id'].endswith('__stop_ego_left_separated'))
        construction_path = HERE / third['construction']
        self.assertEqual(hashlib.sha256(construction_path.read_bytes()).hexdigest(),
                         third['construction_sha256'])
        files = {f['path']: f['content']
                 for f in json.loads(construction_path.read_text())['files']}
        self.assertEqual(json.loads(files['config.json'])['ego_hold_after_clear_frames'], 8)
        self.assertIn('gated_clear=clear', files['runner.py'])
        first = json.loads((HERE / 'primary-compatibility-receipt-v3.json').read_text())
        receipt = json.loads((HERE / third['compatibility']['receipt']).read_text())
        near = first['measurement_examples']['entry_timing']['value']
        separated = receipt['measurement_examples']['entry_timing']['value']
        self.assertAlmostEqual(near['absolute_difference_s'], 0.05)
        self.assertAlmostEqual(separated['absolute_difference_s'], 0.25)
        self.assertEqual(separated['first_body_entry']['ego']['frame'], 106)
        self.assertEqual(separated['first_body_entry']['other']['frame'], 101)
        self.assertEqual(separated['approximately_same_time_judgment'], 'unresolved')
        self.assertEqual(receipt['negative_removed'], 'controller_history.jsonl')
        self.assertEqual([c['changed_knobs'] for c in third['candidates']],
                         [['ego_hold_after_clear_frames'], ['other_release_frame'],
                          ['capture_duration']])
        for candidate in third['candidates']:
            fallback_path = HERE / candidate['construction']
            self.assertEqual(hashlib.sha256(fallback_path.read_bytes()).hexdigest(),
                             candidate['construction_sha256'])
            fallback_receipt = json.loads((HERE / candidate['compatibility']['receipt']).read_text())
            self.assertEqual(fallback_receipt['candidate_id'], candidate['id'])
            self.assertAlmostEqual(fallback_receipt['measurement_examples']['entry_timing']
                                   ['value']['absolute_difference_s'], 0.25)


if __name__ == '__main__':
    unittest.main()
