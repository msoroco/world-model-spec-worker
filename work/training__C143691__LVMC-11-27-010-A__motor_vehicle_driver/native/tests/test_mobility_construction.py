"""CPU checks for the unselected mobility-device construction request."""

import json
from pathlib import Path
import unittest

from runner import check, select_subject_blueprint


HERE = Path(__file__).resolve().parents[2]


class Library:
    def __init__(self, ids):
        self.ids = ids

    def filter(self, pattern):
        if pattern == 'vehicle.*wheelchair*':
            matches = [item for item in self.ids if 'wheelchair' in item]
        elif pattern == 'vehicle.*mobility*':
            matches = [item for item in self.ids if 'mobility' in item]
        else:
            matches = []
        return [type('Blueprint', (), {'id': item})() for item in matches]


class MobilityConstruction(unittest.TestCase):
    def test_exact_unselected_request_and_four_cameras(self):
        construction = json.loads((HERE / 'draft-exact/mobility_device/primary/construction.json').read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        self.assertEqual(config['case_id'].rsplit('__', 1)[-1], 'mobility_device')
        self.assertEqual(config['source_context_request']['exception_kind'], 'mobility_device')
        self.assertEqual(config['actor'], 'motor_vehicle_driver')
        self.assertEqual(check(config)['frames'], 600)
        self.assertEqual(len(config['cameras']), 4)
        self.assertIn('unselected', construction['status'])

    def test_asset_selection_requires_matching_native_blueprint(self):
        eligible_name = 'vehicle.example.mobility_wheelchair'
        self.assertEqual(select_subject_blueprint(Library([eligible_name]), 'mobility_device').id,
                         eligible_name)
        with self.assertRaisesRegex(RuntimeError, 'blueprint unavailable'):
            select_subject_blueprint(Library(['vehicle.tesla.model3']), 'mobility_device')


if __name__ == '__main__':
    unittest.main()
