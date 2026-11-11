import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('opposing_turn_runner', ROOT / 'opposing_turn_runner.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerContractTests(unittest.TestCase):
    def test_primary_and_three_engineering_knobs(self):
        config = json.loads((ROOT / 'config.json').read_text())
        current = runner.check_config(config)
        self.assertEqual(len(current), 3)
        for index, key, value in (
                (0, 'route_step_m', 1.0),
                (1, 'target_speed_mps', 4.0),
                (2, 'overview_height_delta_m', 2.0)):
            variant = dict(config, **{key: value})
            expected = list(current)
            expected[index] = value
            self.assertEqual(runner.check_config(variant), tuple(expected))
        with self.assertRaisesRegex(ValueError, 'route or controller bounds'):
            runner.check_config(dict(config, overview_height_delta_m=4))

    def test_no_device_case_rejects_original_route_signals(self):
        from types import SimpleNamespace as S
        class Map:
            def to_opendrive(self):
                return '<OpenDRIVE><road id="10"><signals><signal id="S1"/></signals></road></OpenDRIVE>'
        class World:
            def get_actors(self):
                return []
        pair = {'subject': {'approach_road_id': 10, 'path': [S(is_junction=True, transform=S(location=None))]},
                'opposing': {'approach_road_id': 10}}
        with self.assertRaisesRegex(ValueError, 'possible governing'):
            runner.device_inventory(World(), Map(), pair)


if __name__ == '__main__':
    unittest.main()
