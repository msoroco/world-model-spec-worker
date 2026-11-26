"""CPU checks for exact bus school-crossing-zone capture identity and survey gate."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('selected_runner', ROOT/'runner.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class ExactBundleTest(unittest.TestCase):
    def test_config(self):
        self.assertEqual(runner.config_check()['case_id'], runner.CASE)

    def test_survey_rejects_missing_sources(self):
        with self.assertRaisesRegex(ValueError, 'Missing reviewed Native survey source'):
            runner.survey_check({})

    def test_capture_is_lazy(self):
        self.assertNotIn('carla', runner.__dict__)

    def test_exact_requested_speed(self):
        expected = {'condition_a': 20, 'at_limit': 25, 'condition_b': 30,
                    'no_school_day': 30, 'half_hour_window': 30,
                    'beacon_not_flashing': 30,
                    'nonbeacon_sign_active': 30,
                    'nonbeacon_sign_inactive': 30}
        suffix = runner.CASE.rsplit('__', 1)[-1]
        config = json.loads((ROOT/'config.json').read_text())
        self.assertEqual(config['target_mph'], expected[suffix])

    def test_review_template_withholds_authority_facts(self):
        survey = {name: 'survey-only-source' for name in (
            'zone_establishment_source', 'installed_sign_source', 'calendar_source',
            'school_hours_source', 'half_hour_window_source', 'beacon_source',
            'beacon_phase_source', 'beacon_lights_source',
            'nonbeacon_sign_schedule_source', 'children_source',
            'motor_bus_class_source', 'civil_time_source',
            'governing_road_direction_source')}
        survey.update(zone_station_bounds_m=[10, 40], road_axis_xy=[1, 0],
                      road_id=42, travel_direction_id='eastbound',
                      authorized_mph=15, civil_start_iso='2026-11-23T08:00:00-08:00',
                      planned_context_source='survey-only-source', planned_context='test plan')
        template = runner.context_template(survey, 7, 'a'*64)
        self.assertEqual(template['case_id'], runner.CASE)
        self.assertEqual(template['travel_direction_id'], 'eastbound')
        self.assertEqual(template['road_id'], 42)
        self.assertIsNone(template['zone_designated'])
        self.assertIsNone(template['beacon_flashing'])
        self.assertIsNone(template['condition_stable_30s'])
        self.assertEqual(template['camera_sha256'], {})
        self.assertEqual(template['native_survey_sha256'], 'a'*64)

    def test_survey_binds_case_and_civil_clock(self):
        config = json.loads((ROOT/'config.json').read_text())
        source_names = ('survey_source', 'zone_establishment_source', 'installed_sign_source',
                        'calendar_source', 'school_hours_source', 'half_hour_window_source',
                        'beacon_source', 'beacon_phase_source', 'beacon_lights_source',
                        'nonbeacon_sign_schedule_source', 'children_source',
                        'civil_time_source', 'motor_bus_class_source', 'zone_boundary_source',
                        'governing_road_direction_source', 'planned_context_source')
        survey = {name: 'reviewed local source' for name in source_names}
        survey.update(map_name='surveyed local map', ego_blueprint='vehicle.heavy',
                      spawn_xyz_m=[0, 0, 1], spawn_yaw_deg=0,
                      camera_world_transforms={name: {'xyz_m': [0, 0, 2],
                                                     'rotation_deg': [0, 0, 0]}
                                               for name in runner.CAMERAS},
                      road_axis_xy=[1, 0], zone_station_bounds_m=[10, 40],
                      civil_start_iso='2026-11-23T08:00:00-08:00', authorized_mph=25,
                      road_id=42, travel_direction_id='eastbound',
                      child_blueprints={'child_left': 'walker.a', 'child_right': 'walker.b'},
                      child_world_transforms={name: {'xyz_m': [0, 0, 0],
                                                     'rotation_deg': [0, 0, 0]}
                                              for name in ('child_left', 'child_right')},
                      reviewed_plan_case_id=runner.CASE,
                      planned_context=config['planned_context'],
                      installed_sign_geometry={'actor_id': 201, 'asset_id': 'surveyed-sign',
                                               'geometry_source': 'surveyed actor transform and image',
                                               'sign_kind': 'school_crossing_zone_speed_limit_25_mph',
                                               'xyz_m': [20, 0, 2]})
        if config['planned_context'] not in ('nonbeacon_sign_active', 'nonbeacon_sign_inactive'):
            survey['beacon_geometry'] = {
                'sign_actor_id': 201, 'geometry_source': 'surveyed beacon actor transforms',
                'alternation_controller_source': 'source-identified beacon controller',
                'yellow_lights': [
                    {'actor_id': 202, 'asset_id': 'yellow-left', 'color': 'yellow', 'xyz_m': [20, -0.5, 3]},
                    {'actor_id': 203, 'asset_id': 'yellow-right', 'color': 'yellow', 'xyz_m': [20, 0.5, 3]}]}
        self.assertEqual(runner.survey_check(survey), survey)
        with self.assertRaisesRegex(ValueError, 'Installed sign outside surveyed camera source view'):
            runner.survey_check({**survey, 'installed_sign_geometry': {
                **survey['installed_sign_geometry'], 'xyz_m': [-20, 0, 2]}})
        if 'beacon_geometry' in survey:
            with self.assertRaisesRegex(ValueError, 'two or more distinct alternating yellow lights'):
                runner.survey_check({**survey, 'beacon_geometry': {
                    **survey['beacon_geometry'], 'yellow_lights': survey['beacon_geometry']['yellow_lights'][:1]}})
        with self.assertRaisesRegex(ValueError, 'exact planned school-crossing-zone condition'):
            runner.survey_check({**survey, 'reviewed_plan_case_id': 'another case'})
        with self.assertRaisesRegex(ValueError, 'civil start needs timezone'):
            runner.survey_check({**survey, 'civil_start_iso': '2026-11-23T08:00:00'})
