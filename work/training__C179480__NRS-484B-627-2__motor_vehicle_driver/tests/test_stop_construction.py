import importlib.util
from pathlib import Path
import unittest


path = Path(__file__).resolve().parents[1] / 'stop_construction.py'
spec = importlib.util.spec_from_file_location('c179480_stop_construction', path)
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class StopConstructionTest(unittest.TestCase):
    def test_two_targets_change_lane_overlap_only(self):
        road = module.RoadProfile(3.7, 3.0, 1.9)
        blocked = module.target(road, True)
        clear = module.target(road, False)
        self.assertTrue(blocked['planned_lane_overlap'])
        self.assertFalse(clear['planned_lane_overlap'])
        self.assertEqual(blocked['approaching_actor_lateral_m'],
                         clear['approaching_actor_lateral_m'])
        self.assertGreater(clear['ego_stop_lateral_m'],
                           blocked['ego_stop_lateral_m'])
        for field in ('safe_operation_necessity', 'compliance_with_law',
                      'actual_impediment'):
            self.assertEqual(blocked[field], 'measure_from_original_sources')

    def test_rejects_shoulder_that_cannot_clear_lane(self):
        with self.assertRaisesRegex(ValueError, 'cannot clear'):
            module.target(module.RoadProfile(3.7, 2.0, 1.9), False)

    def test_rejects_non_boolean_selection(self):
        with self.assertRaisesRegex(ValueError, 'exact Boolean'):
            module.target(module.RoadProfile(3.7, 3.0, 1.9), 1)


if __name__ == '__main__':
    unittest.main()
