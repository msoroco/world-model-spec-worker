import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from highway_continuity_runner import CASE, check_config, select_native_pair
from test_categorical_highway_points import Point, native_map


class HighwayContinuityRunnerTests(unittest.TestCase):
    def test_exact_identity_and_four_camera_profile(self):
        config = json.loads((ROOT / 'config.json').read_text())
        config.update(selected_case_id=CASE, subject_category='continuing')
        check_config(config)
        wrong = copy.deepcopy(config)
        wrong['cameras'][0]['width'] -= 1
        with self.assertRaisesRegex(ValueError, 'cameras'):
            check_config(wrong)

    def test_native_pair_uses_one_through_route_and_rejects_control(self):
        world, ending, through = native_map(subject_continues=False)
        continuing = [Point(-8, 4, 1, 0, 7), Point(0, 4, 1, 0, 8, True),
                      Point(6, 4, 1, 0, 7)]
        for first, second in zip(continuing, continuing[1:]):
            first.successors = [second]
        starts = {id(path[0].transform.location): path[0]
                  for path in (ending, continuing, through)}
        world.get_spawn_points = lambda: [NS(location=path[0].transform.location)
                                          for path in (ending, continuing, through)]
        world.get_waypoint = lambda location: starts[id(location)]
        with patch('highway_continuity_runner.extend_exit', side_effect=lambda p: p):
            pair = select_native_pair(world, [])
            self.assertIs(pair['continuing'][-1], continuing[-1])
            self.assertIs(pair['other'][0], through[0])
            continuing[0].landmarks = [NS(id='control-1', type='206')]
            with self.assertRaisesRegex(ValueError, 'No controlled'):
                select_native_pair(world, [])


if __name__ == '__main__':
    unittest.main()
