from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_median_opening_probe import check_config
from test_median_opening_route import reference


CASE = 'heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__baseline_right_east'


class NativeMedianOpeningProbeTests(unittest.TestCase):
    def test_requires_exact_sourced_opening_and_probe_only(self):
        config = {'selected_case_id': CASE, 'law_id': 'NRS-484B-200-1',
                  'cell_id': 'C125714', 'actor': 'motor_vehicle_driver',
                  'rate_hz': 20, 'frames': 80, 'travel_direction': 'east',
                  'construction_probe_only': True,
                  'median_opening_reference': {**reference(),
                                               'travel_direction': 'east'}}
        check_config(config)
        with self.assertRaisesRegex(ValueError, 'map source required'):
            check_config({**config, 'median_opening_reference': None})
        with self.assertRaisesRegex(ValueError, 'direction differs'):
            check_config({**config, 'median_opening_reference': {
                **config['median_opening_reference'], 'travel_direction': 'west'}})
        with self.assertRaisesRegex(ValueError, 'masquerade'):
            check_config({**config, 'construction_probe_only': False})


if __name__ == '__main__':
    unittest.main()
