import copy
import json
import unittest
from pathlib import Path

from runner import check
from capture_feature import phase, generation_parameters


class ExactSelectedFeature(unittest.TestCase):
    def setUp(self):
        self.bundle = Path.cwd()
        self.config = json.loads((self.bundle / 'config.json').read_text())

    def test_exact_source_owned_request(self):
        got = check(self.bundle)
        self.assertEqual(got['frames'], 600)
        self.assertFalse(got['native_executed'])
        self.assertEqual(len([phase(self.config, frame) for frame in range(600)]), 600)

    def test_missing_source_is_rejected(self):
        import runner
        original = runner.sha
        try:
            runner.sha = lambda path: 'wrong' if Path(path).name == 'assignment-source.json' else original(path)
            with self.assertRaisesRegex(ValueError, 'source changed'):
                check(self.bundle)
        finally:
            runner.sha = original

    def test_reject_invented_physical_claim(self):
        from draft_runner import check as geometry
        altered = copy.deepcopy(self.config)
        altered['physical_verified'] = True
        with self.assertRaisesRegex(ValueError, 'invented'):
            geometry(altered, (self.bundle / 'road.xodr').read_text())

    def test_reject_short_controller(self):
        altered = copy.deepcopy(self.config)
        altered['control_phases'][-1]['last_frame'] = 598
        with self.assertRaisesRegex(ValueError, 'control phase'):
            phase(altered, 599)

    def test_exact_roadside_occluder_request(self):
        class Carla:
            @staticmethod
            def OpendriveGenerationParameters(**options):
                return options

        params = generation_parameters(Carla, self.config)
        self.assertEqual(params['wall_height'], 4.0)
        self.assertEqual(params['additional_width'], 0)
        self.assertTrue(params['enable_mesh_visibility'])
        for bad_height in (None, 0, 3.9):
            changed = dict(self.config)
            changed['roadside_wall_height_m'] = bad_height
            with self.assertRaisesRegex(ValueError, 'occluder geometry'):
                generation_parameters(Carla, changed)
