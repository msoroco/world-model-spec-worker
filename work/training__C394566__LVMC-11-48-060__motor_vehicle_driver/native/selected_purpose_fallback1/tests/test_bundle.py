"""CPU-only route configuration and survey tests."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('selected_runner', ROOT/'runner.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class BundleTests(unittest.TestCase):
    def test_config(self):
        self.assertEqual(runner.config_check()['case_id'], runner.CASE)

    def test_survey_rejects_missing_sources(self):
        with self.assertRaisesRegex(ValueError, 'Missing reviewed Native survey source'):
            runner.survey_check({})

    def test_service_waypoint_must_be_internal(self):
        survey = {'map_name': 'synthetic', 'survey_source': 'synthetic',
                  'truck_blueprint_source': 'synthetic', 'truck_route_designation_source': 'synthetic',
                  'nontruck_street_designation_source': 'synthetic', 'route_connectivity_source': 'synthetic',
                  'vehicle_blueprint': 'vehicle.truck.synthetic', 'entry_truck_route_id': 100,
                  'intervening_street_id': 200, 'exit_truck_route_id': 300,
                  'spawn_xyz_m': [0, 0, 0], 'spawn_yaw_deg': 0,
                  'route_waypoints_xyz_m': [[0, 0, 0], [10, 0, 0], [20, 0, 0]],
                  'camera_mounts': {name: {'xyz_m': [0, 0, 0], 'rotation_deg': [0, 0, 0]}
                                    for name in runner.CAMERAS},
                  'served_premises_source': 'synthetic', 'enroute_service_waypoint_index': 1}
        self.assertIs(runner.survey_check(survey), survey)
        survey['enroute_service_waypoint_index'] = 2
        with self.assertRaisesRegex(ValueError, 'Invalid surveyed service waypoint'):
            runner.survey_check(survey)


if __name__ == '__main__':
    unittest.main()
