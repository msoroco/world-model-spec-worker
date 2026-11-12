"""Exact one-way selected case and capture contract."""
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from one_way_runner import check_config

CASE = 'heldout__C230259__NRS-484B-200-1__motor_vehicle_driver__one_way_left'


class OneWayConfigTest(unittest.TestCase):
    def test_exact_case_and_fixed_duration(self):
        config = json.loads((HERE / 'config.json').read_text())
        config['selected_case_id'] = CASE
        config['case']['case_id'] = CASE
        self.assertEqual(check_config(config), 'left')
        config['frames'] = 81
        with self.assertRaisesRegex(ValueError, '80 original frames'):
            check_config(config)
        config['frames'] = 80
        config['selected_case_id'] = CASE.replace('one_way_left', 'baseline_left')
        with self.assertRaisesRegex(ValueError, 'only exact one-way'):
            check_config(config)
