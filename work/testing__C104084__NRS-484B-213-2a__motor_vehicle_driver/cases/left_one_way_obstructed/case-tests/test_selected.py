import json
import unittest
from pathlib import Path

class SelectedCaseTests(unittest.TestCase):
    def test_exact_config_and_four_view_contract(self):
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(config['selected_case_id'], 'testing__C104084__NRS-484B-213-2a__motor_vehicle_driver__left_one_way_obstructed')
        self.assertEqual(config['rate_hz'], 20)
        self.assertEqual(config['duration_s'], 45)
        self.assertEqual([c['name'] for c in config['cameras']], ['overview','approach','reference_corner','driver_reference'])
        self.assertEqual(len(config['case']['recording_description']['channels']), 7)
