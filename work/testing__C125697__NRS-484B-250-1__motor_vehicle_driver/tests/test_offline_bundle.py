import hashlib
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
AID = ROOT.name


class OfflineBundleTests(unittest.TestCase):
    def test_two_exact_case_constructions_and_source_seals(self):
        manifest = json.loads((ROOT / 'execution-manifest.draft.json').read_text())
        cases = {AID + '__precedence', AID + '__advance'}
        self.assertEqual({row['case_id'] for row in manifest['cases']}, cases)
        for row in manifest['cases']:
            path = ROOT / row['construction']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                             row['construction_sha256'])
            package = json.loads(path.read_text())
            files = {item['path']: item['content'] for item in package['files']}
            config = json.loads(files['config.json'])
            self.assertEqual(config['selected_case_id'], row['case_id'])
            suffix = row['case_id'].rsplit('__', 1)[1]
            self.assertEqual(config['requested_ego_response'],
                             'yield_before_entry' if suffix == 'precedence'
                             else 'advance_before_other_exit')
            self.assertEqual(files['median_opening.py'],
                             (ROOT / 'median_opening.py').read_text())
            self.assertEqual(config['plan_sha256'], hashlib.sha256(
                (ROOT / 'case-plan.json').read_bytes()).hexdigest())
            self.assertEqual(config['required_sources'],
                             ['native_trace', 'opendrive', 'device_inventory',
                              'camera_overview', 'camera_approach',
                              'camera_reference_corner', 'camera_driver_reference'])
            self.assertTrue(package['diagnostic_only'])
            self.assertEqual(config['frame_count'], 900)
            self.assertEqual(config['rate_hz'], 20)


if __name__ == '__main__':
    unittest.main()
