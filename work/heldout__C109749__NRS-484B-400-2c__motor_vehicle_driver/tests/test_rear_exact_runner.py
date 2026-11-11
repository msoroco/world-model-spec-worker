import json
import unittest
from pathlib import Path
from types import SimpleNamespace as S

from opposing_turn_rear_runner import check_config, device_inventory


class RearRunnerTests(unittest.TestCase):
    def test_exact_rear_config_and_scope(self):
        local = Path(__file__).resolve().parents[1]
        source = local / 'config-rear_pass_no_device.json'
        config = json.loads((source if source.exists() else local / 'config.json').read_text())
        self.assertEqual(check_config(config), (
            float(config.get('route_step_m', 2.)),
            float(config.get('target_speed_mps', 5.)),
            float(config.get('overview_height_delta_m', 0.))))
        self.assertEqual(config['rear_policy']['subject_release_delay_ticks'], 2)
        config['selected_case_id'] = config['selected_case_id'].replace(
            '__rear_pass_no_device', '__front_pass_no_device')
        with self.assertRaisesRegex(ValueError, 'rear Native runner'):
            check_config(config)

    def test_uncontrolled_rear_rejects_route_signal(self):
        class Map:
            def to_opendrive(self):
                return '<OpenDRIVE><road id="10"><signals><signal id="S1"/></signals></road></OpenDRIVE>'
        class World:
            def get_actors(self):
                return []
        pair = {'subject': {'approach_road_id': 10,
                            'path': [S(is_junction=True, transform=S(location=None))]},
                'opposing': {'approach_road_id': 10}}
        with self.assertRaisesRegex(ValueError, 'possible governing'):
            device_inventory(World(), Map(), pair)


if __name__ == '__main__':
    unittest.main()
