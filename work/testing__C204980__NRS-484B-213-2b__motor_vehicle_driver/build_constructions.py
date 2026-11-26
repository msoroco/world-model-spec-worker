"""Bind the six exact rail cases to inline Native constructions."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
LAW = 'NRS-484B-213-2b'
CELL = 'C204980'
MODULES = ('runner.py', 'rail_left.py', 'reviewed_rail.py',
           'rail_capture.py', 'carla_rail_adapter.py', 'canonical_bridge.py',
           'analysis.py')
CHANNELS = ('rail_qualification', 'highway_direction', 'crossing_extent',
            'ego_body_side_and_station', 'original_frame_and_camera_join')
CAMERAS = (
    ('overview', 1920, 1080, 'fixed elevated crossing and whole 100-foot approach'),
    ('approach', 1280, 720, 'fixed ego body and near crossing edge'),
    ('reference_corner', 1280, 720, 'fixed centerline and both crossing edges'),
    ('driver_reference', 1280, 720, 'ego-attached crossing sight line'),
)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False,
                               sort_keys=True) + '\n', encoding='utf-8')


def description():
    return {'channels': [{'name': name, 'unit': 'structured record',
             'sampling_rate_hz': 20,
             'method': 'Source-hashed original CARLA rail site/body and four-camera frame join',
             'time_window': 'entire 45-second approach and crossing traversal',
             'reference_frame': 'reviewed highway centerline and crossing stations',
             'uncertainty': '20 Hz sampling, body-bounding-box reference and source map geometry'}
             for name in CHANNELS], 'context_inputs': [],
            'limitations': [
             'A source-reviewed stationary-rail carrier and at-grade crossing are required.',
             'Leading-body/near-edge distance is an engineering measurement, not a legal definition.',
             'Actual motion, pixels and legal interpretation remain for independent local review.']}


def config(case, all_ids, candidate='primary'):
    cid = case['case_id']
    suffix = cid.removeprefix(AID + '__')
    return {'assignment_id': AID, 'law_id': LAW, 'cell_id': CELL,
            'actor': 'motor_vehicle_driver', 'selected_case_id': cid,
            'supported_case_ids': all_ids, 'rate_hz': 20, 'duration_s': 45,
            'required_atoms': [], 'source_packets': [],
            'reviewed_packet': ('reviewed-packet.json' if candidate == 'primary'
                                else 'reviewed-fallback1-packet.json'),
            'reviewed_source_root': 'reviewed-sources',
            'case': {'case_id': cid, 'target_leading_distance_ft': case['target_leading_distance_ft'],
                     'left_side_requested': case['left_side_requested'],
                     'one_way_highway': case['one_way_highway'],
                     'recording_description': description()},
            'cameras': [{'name': name, 'width': width, 'height': height,
                         'fov_deg': 90, 'pose_strategy': strategy}
                        for name, width, height, strategy in CAMERAS],
            'physical_completion': {'criterion': 'travel_progress',
                                    'motion_source': 'trace.jsonl',
                                    'position_key': 'position_m',
                                    'minimum_progress_m': 10,
                                    'minimum_samples': 2,
                                    'engineering_tolerances_not_legal': True},
            'comparison_policy': 'same reviewed route, speed controller and camera contract across linked cases',
            'candidate_id': candidate,
            'case_suffix': suffix}


def selected_test(cid):
    return ('import json\nimport unittest\nfrom pathlib import Path\n\n'
            'class ExactRailCaseTest(unittest.TestCase):\n'
            '    def test_selected_case_and_camera_contract(self):\n'
            '        cfg=json.loads(Path("config.json").read_text())\n'
            f'        self.assertEqual(cfg["selected_case_id"],{cid!r})\n'
            '        self.assertEqual(cfg["rate_hz"]*cfg["duration_s"],900)\n'
            '        self.assertEqual([x["name"] for x in cfg["cameras"]],'
            '["overview","approach","reference_corner","driver_reference"])\n')


def construction(case, all_ids, location, candidate='primary'):
    cid = case['case_id']
    cfg = config(case, all_ids, candidate)
    write(location / 'config.json', cfg)
    test_path = location / 'case-tests' / 'test_selected.py'
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text(selected_test(cid), encoding='utf-8')
    modules = [{'path': name, 'source': str((HERE / name).relative_to(REPO)),
                'content': (HERE / name).read_text(encoding='utf-8')}
               for name in MODULES]
    modules.extend((
        {'path': 'config.json', 'source': str((location / 'config.json').relative_to(REPO)),
         'content': (location / 'config.json').read_text(encoding='utf-8')},
        {'path': 'tests/test_selected.py',
         'source': str(test_path.relative_to(REPO)),
         'content': test_path.read_text(encoding='utf-8')},
    ))
    return {'law_id': LAW, 'cell_id': CELL, 'actor': 'motor_vehicle_driver',
            'case_id': cid, 'entrypoint': 'runner.py', 'files': modules,
            'recording_description': description(),
            'mechanisms': ['source-reviewed live OpenDRIVE and qualifying at-grade railroad gate',
                           'actual ego spawn and original centerline/body route control',
                           '20 Hz four-camera Native capture and sealed original source packets'],
            'measurement_plan': {
                'left_side': 'original body-corner lateral extent relative to reviewed highway centerline',
                'distance': 'original leading body station to reviewed near crossing edge in feet',
                'traversal': 'original leading/trailing body overlap with reviewed grade-crossing extent',
                'one_way': 'original authority document and live map binding; legal effect unresolved'},
            'static_checks': ['reviewed packet and source hashes before world mutation',
                              'exact case and live OpenDRIVE identity',
                              '900 original body/camera/graph frame and time joins'],
            'termination_rules': ['45-second 900-frame synchronized capture',
                                  'close encoders and graph, destroy owned actors and sensors, restore world settings']}


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    cases = plan['cases']
    ids = [case['case_id'] for case in cases]
    for index, case in enumerate(cases):
        suffix = case['case_id'].removeprefix(AID + '__')
        location = HERE if index == 0 else HERE / 'cases' / suffix
        write(location / 'construction.json', construction(case, ids, location))
        fallback = HERE / 'fallbacks' / suffix
        write(fallback / 'construction.json', construction(case, ids, fallback,
                                                           candidate='fallback1'))
    print(json.dumps({'assignment_id': AID, 'primary_cases': len(cases),
                      'source_reviewed_fallbacks': len(cases)}, sort_keys=True))


if __name__ == '__main__':
    main()
