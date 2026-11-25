"""Bind exact source-gated C104084 Native implementations into four inline cases."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
LAW = 'NRS-484B-213-2a'
CELL = 'C104084'
MODULES = (
    'runner.py', 'carla_delegate.py', 'canonical_bridge.py',
    'native_capture.py', 'native_source_adapter.py', 'native_map.py',
    'crest_geometry.py', 'saved_crest.py', 'analysis.py',
    'derived_audit.py', 'delivery_media.py', 'saved_delivery.py',
    'delivery_audit.py', 'comparison_audit.py',
)
CHANNELS = (
    'original_lane_directions', 'crest_grade_profile',
    'ego_left_side_body_history', 'opposing_vehicle_route_and_body',
    'driver_view_proxy_and_visibility', 'highway_one_way_context',
    'frame_and_camera_join',
)
CAMERAS = (
    ('overview', 1920, 1080, 'fixed elevated full approach and grade'),
    ('approach', 1280, 720, 'fixed approaching ego and opposing vehicle'),
    ('reference_corner', 1280, 720, 'fixed center reference and crest'),
    ('driver_reference', 1280, 720, 'ego attached driver reference'),
)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False,
                               sort_keys=True) + '\n', encoding='utf-8')


def description():
    return {'channels': [{'name': name, 'unit': 'structured record',
             'sampling_rate_hz': 20,
             'method': 'Original Native map, body, ray and camera frame join',
             'time_window': 'entire 45-second crest approach',
             'reference_frame': 'original CARLA world and reviewed road center',
             'uncertainty': '20 Hz sampling, map geometry and camera perspective'}
             for name in CHANNELS], 'context_inputs': [],
            'limitations': [
             'Proxy rays and sampled grade do not establish actual driver perception.',
             'Public highway and one-way designation require reviewed original records.',
             'Hazard distance remains a legal judgment without an invented cutoff.']}


def config(case_id, cases):
    suffix = case_id.removeprefix(ASSIGNMENT + '__')
    return {'assignment_id': ASSIGNMENT, 'law_id': LAW, 'cell_id': CELL,
            'actor': 'motor_vehicle_driver', 'selected_case_id': case_id,
            'supported_case_ids': cases, 'rate_hz': 20, 'duration_s': 45,
            'required_atoms': [], 'source_packets': [],
            'reviewed_packet': 'reviewed-packet.json',
            'reviewed_source_root': 'reviewed-sources',
            'case': {'case_id': case_id,
                     'ego_left_side_requested': suffix != 'right_crest_obstructed',
                     'sampled_grade_blocked_requested': suffix != 'left_crest_clear',
                     'one_way_requested': suffix == 'left_one_way_obstructed',
                     'recording_description': description()},
            'cameras': [{'name': name, 'width': width, 'height': height,
                         'fov_deg': 90, 'pose_strategy': strategy}
                        for name, width, height, strategy in CAMERAS],
            'physical_completion': {'criterion': 'travel_progress',
                                    'motion_source': 'trace.jsonl',
                                    'position_key': 'position_m',
                                    'minimum_progress_m': 20,
                                    'minimum_samples': 2}}


def case_test(case_id):
    return ("import json\nimport unittest\nfrom pathlib import Path\n\n"
            "class SelectedCaseTests(unittest.TestCase):\n"
            "    def test_exact_config_and_four_view_contract(self):\n"
            "        config = json.loads(Path('config.json').read_text())\n"
            f"        self.assertEqual(config['selected_case_id'], {case_id!r})\n"
            "        self.assertEqual(config['rate_hz'], 20)\n"
            "        self.assertEqual(config['duration_s'], 45)\n"
            "        self.assertEqual([c['name'] for c in config['cameras']], "
            "['overview','approach','reference_corner','driver_reference'])\n"
            "        self.assertEqual(len(config['case']['recording_description']['channels']), 7)\n")


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    cases = [item['case_id'] for item in plan['cases']]
    for index, case_id in enumerate(cases):
        suffix = case_id.removeprefix(ASSIGNMENT + '__')
        location = HERE if index == 0 else HERE / 'cases' / suffix
        cfg = config(case_id, cases)
        write(location / 'config.json', cfg)
        test_path = location / 'case-tests' / 'test_selected.py'
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text(case_test(case_id), encoding='utf-8')
        implementation = [{'path': name, 'source': str((HERE / name).relative_to(REPO)),
                           'content': (HERE / name).read_text(encoding='utf-8')}
                          for name in MODULES]
        implementation.extend((
            {'path': 'config.json', 'source': str((location / 'config.json').relative_to(REPO)),
             'content': (location / 'config.json').read_text(encoding='utf-8')},
            {'path': 'tests/test_selected.py',
             'source': str(test_path.relative_to(REPO)),
             'content': test_path.read_text(encoding='utf-8')},
        ))
        construction = {'law_id': LAW, 'cell_id': CELL,
                        'actor': 'motor_vehicle_driver', 'case_id': case_id,
                        'entrypoint': 'runner.py', 'files': implementation,
                        'recording_description': description(),
                        'mechanisms': ['reviewed original road-grade selection',
                                       'live two-vehicle route control',
                                       'source-hashed Native body/ray and four-view capture'],
                        'measurement_plan': {
                            'left_side': 'Original signed body corners relative to reviewed center',
                            'crest_view': 'Original map grade and live four-corner ray join',
                            'one_way': 'Original reviewed lane allocation and authority source',
                            'hazard_distance': 'Retain original opposing distance without legal cutoff'},
                        'static_checks': ['source review before Native world mutation',
                                          'exact four camera and source frame joins',
                                          'clear or obstructed original sampled road-grade condition'],
                        'termination_rules': ['45-second 900-frame synchronized capture',
                                              'always restore Native world and release owners']}
        write(location / 'construction.json', construction)
    print(json.dumps({'assignment_id': ASSIGNMENT, 'cases_built': cases},
                     sort_keys=True))


if __name__ == '__main__':
    main()
