"""CPU checks for exact route capture identity and mandatory survey."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('selected_runner', ROOT/'runner.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_config():
    assert runner.config_check()['case_id'] == runner.CASE


def test_survey_rejects_missing_sources():
    try:
        runner.survey_check({})
    except ValueError as exc:
        assert 'Missing reviewed Native survey source' in str(exc)
    else:
        raise AssertionError('unsourced survey accepted')


def test_service_waypoint_must_be_internal_to_reviewed_route():
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
    assert runner.survey_check(survey) is survey
    survey['enroute_service_waypoint_index'] = 2
    try:
        runner.survey_check(survey)
    except ValueError as exc:
        assert 'Invalid surveyed service waypoint' in str(exc)
    else:
        raise AssertionError('Endpoint service stop accepted')
