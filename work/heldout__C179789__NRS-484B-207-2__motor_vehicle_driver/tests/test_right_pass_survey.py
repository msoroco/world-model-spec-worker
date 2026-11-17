import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('right_pass_survey', ROOT / 'right_pass_survey.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.path.insert(0, str(ROOT))
native_spec = importlib.util.spec_from_file_location('overtaken_native_survey', ROOT / 'overtaken_native.py')
native = importlib.util.module_from_spec(native_spec)
native_spec.loader.exec_module(native)


class Waypoint:
    road_id = 7
    lane_id = -1
    lane_width = 3.5
    is_junction = False
    def get_right_lane(self):
        lane = Waypoint()
        lane.lane_id = -2
        return lane


class SurveyTests(unittest.TestCase):
    def test_native_map_facts_are_recorded_without_permission_inference(self):
        result = module.collect('Town01', Waypoint(), 100, 5.0, [11, 12])
        self.assertEqual(result['lane_ids'], [-1, -2])
        self.assertEqual(result['road_id'], 7)
        self.assertIsNone(result['permission_state'])
        self.assertIsNone(result['pavement_unobstructed'])
        self.assertIsNone(result['safety_condition_verified'])

    def test_missing_original_waypoint_and_invalid_width_rejected(self):
        with self.assertRaisesRegex(ValueError, 'waypoint missing'):
            module.collect('Town01', None, 100, 5.0, [])
        bad = Waypoint()
        bad.lane_width = float('nan')
        with self.assertRaisesRegex(ValueError, 'geometry invalid'):
            module.collect('Town01', bad, 100, 5.0, [])

    def test_native_writes_original_survey_once_and_preserves_unknown_permission(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = native.write_right_pass_survey(tmp, 'Town01', Waypoint(), 100, 5.0, [11, 12])
            saved = json.loads(path.read_text())
            self.assertEqual(saved['frame'], 100)
            self.assertEqual(saved['observed_vehicle_ids'], [11, 12])
            self.assertIsNone(saved['permission_state'])
            self.assertIsNone(saved['legal_conclusion'])
            with self.assertRaises(FileExistsError):
                native.write_right_pass_survey(tmp, 'Town01', Waypoint(), 101, 5.05, [11, 12])


if __name__ == '__main__':
    unittest.main()
