import json
import unittest
from pathlib import Path
from runner import check
from geometry import open_drive
from controller import command

class TaxiNative(unittest.TestCase):
    def test_exact_geometry_and_source_profile(self):
        result = check(json.loads(Path('config.json').read_text()))
        self.assertEqual(result['geometry']['first_choices'], [11, 12])
        self.assertFalse(result['physical_completion_claimed'])
        self.assertIn('taxicab-stand-draft', open_drive())
        self.assertIn('right-turn-notice-draft', open_drive())
    def test_controller_split(self):
        self.assertNotEqual(command('right', 79, -1.75, 0, 5)['target_xy_m'],
                            command('straight', 79, -1.75, 0, 5)['target_xy_m'])
