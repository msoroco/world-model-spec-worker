import json
import unittest
from pathlib import Path
from native_red import check_plan, check_map, requested_speed


class ExactNativeRed(unittest.TestCase):
    def test_exact_plan_and_route(self):
        cfg = json.loads(Path('config.json').read_text())
        self.assertEqual(check_plan(cfg)['frames'], 600)
        self.assertEqual(check_map()['roadway_y_abs_max_m'], 3.5)
        self.assertEqual(requested_speed(cfg['condition'], 0), 0)
        self.assertEqual(requested_speed(cfg['condition'], 220) > 0,
                         cfg['requested_entry'])
