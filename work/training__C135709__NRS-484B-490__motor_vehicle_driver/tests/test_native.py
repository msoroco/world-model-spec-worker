"""Focused CPU checks for the exact two-case Native request and source gate."""
import json
import tempfile
import unittest
from pathlib import Path

from geometry import DEVICE_NAME, GOVERNED_X_M, PARK_X_M, check as geometry_check, open_drive
from runner import check as runner_check, validate_source_review

HERE = Path(__file__).resolve().parents[1]


class NativePreparationTests(unittest.TestCase):
    def test_two_case_geometry_and_device(self):
        geometry = geometry_check()
        self.assertEqual(geometry['lane_width_m'], 2.8)
        self.assertIn(DEVICE_NAME, open_drive())
        self.assertGreater(PARK_X_M['probe_01'], GOVERNED_X_M[1])
        self.assertLess(GOVERNED_X_M[0], PARK_X_M['probe_02'])
        self.assertGreater(GOVERNED_X_M[1], PARK_X_M['probe_02'])
        base = json.loads((HERE / 'config.json').read_text())
        for suffix in ('probe_01', 'probe_02'):
            config = dict(base, case_id=base['case_id'].rsplit('__', 1)[0] + '__' + suffix,
                          parking_x_m=PARK_X_M[suffix])
            self.assertEqual(runner_check(config)['frames'], 600)

    def test_request_cannot_claim_original_authority(self):
        config = json.loads((HERE / 'config.json').read_text())
        config['physical_verified'] = True
        with self.assertRaisesRegex(ValueError, 'cannot establish physical'):
            runner_check(config)

    def test_original_scene_review_needs_hashed_sources(self):
        config = json.loads((HERE / 'config.json').read_text())
        review = {'source_kind': 'original_scene_setup', 'case_id': config['case_id'],
                  'map_name': 'synthetic-test', 'device_id': '490',
                  'governed_extent_xyxy_m': [-20, -4, 20, 0],
                  'physical_verified': False, 'legal_verdict': None,
                  'sources': {}}
        with self.assertRaisesRegex(ValueError, 'sources required'):
            validate_source_review(review, config)
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'road.txt'
            source.write_text('synthetic test only\n')
            review['sources'] = {key: {'path': str(source), 'sha256': 'wrong'}
                                 for key in ('highway', 'narrow_designation',
                                             'official_authority', 'device_erection',
                                             'governed_extent')}
            with self.assertRaisesRegex(ValueError, 'source changed'):
                validate_source_review(review, config)


if __name__ == '__main__':
    unittest.main()
