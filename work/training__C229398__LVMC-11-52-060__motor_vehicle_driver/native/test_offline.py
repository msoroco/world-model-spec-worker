"""CPU checks for the exact C229398 draft capture bundle."""
import copy
import json
from pathlib import Path
import unittest

from runner import check, projection_ft, FRAMES, RATE_HZ, TARGETS, VIEWS


HERE = Path(__file__).resolve().parent.parent


class Offline(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((HERE / 'config.json').read_text())

    def test_full_capture_and_original_source_inventory(self):
        receipt = check(self.config)
        self.assertEqual((receipt['frames'], receipt['rate_hz']), (600, 20))
        self.assertEqual((FRAMES, RATE_HZ), (600, 20))
        self.assertEqual(tuple(receipt['camera_views']), VIEWS)
        self.assertFalse(receipt['curb_reviewed'])
        self.assertFalse(receipt['physical_acceptance_claimed'])

    def test_each_boundary_case_has_exact_identity(self):
        for suffix, target in TARGETS.items():
            config = copy.deepcopy(self.config)
            config['case_suffix'] = suffix
            config['case_id'] = config['case_id'].rsplit('__', 1)[0] + '__' + suffix
            config['selected_case_id'] = config['case_id']
            config['target_projection_ft'] = target
            self.assertEqual(check(config)['target_projection_ft'], target)

    def test_case_and_camera_tamper_rejected(self):
        for key, bad in [('law_id', 'LVMC-11-52-061'),
                         ('duration_s', 12), ('target_projection_ft', 200)]:
            config = copy.deepcopy(self.config)
            config[key] = bad
            with self.assertRaises(ValueError):
                check(config)
        config = copy.deepcopy(self.config)
        config['cameras'][2]['name'] = 'duplicate'
        with self.assertRaisesRegex(ValueError, 'Four source cameras'):
            check(config)

    def test_measurement_uses_load_and_trailer_vertices(self):
        def actor(center):
            return {'actor_id': str(center), 'center_xy_m': [center, 0],
                    'half_extent_xy_m': [0.1, 0.1], 'yaw_deg': 0}
        actors = {'vehicle': actor(1), 'load': actor(2), 'trailer': actor(3)}
        self.assertGreater(projection_ft(actors, [0, 0], [1, 0]),
                           projection_ft({**actors, 'trailer': actor(1)},
                                         [0, 0], [1, 0]))


if __name__ == '__main__':
    unittest.main()
