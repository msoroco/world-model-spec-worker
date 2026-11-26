"""Bind two unselected walking comparisons to exact inline construction hashes."""

import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
CASE = 'training__C230259__NRS-484B-297-2__pedestrian__selected_81846e7f__condition_'
CAMERAS = [
    {'name': 'overview', 'width': 1920, 'height': 1080, 'fps': 20, 'fov_deg': 95,
     'pose_strategy': 'vehicle-relative high overview of both participants and highway sides',
     'location_xyz_m': [-7, 0, 5], 'rotation_pyr_deg': [-20, 0, 0]},
    {'name': 'approach', 'width': 1280, 'height': 720, 'fps': 20, 'fov_deg': 85,
     'pose_strategy': 'vehicle-relative forward view of pedestrian approach',
     'location_xyz_m': [3, 0, 2], 'rotation_pyr_deg': [-4, 0, 0]},
    {'name': 'reference_corner', 'width': 1280, 'height': 720, 'fps': 20, 'fov_deg': 90,
     'pose_strategy': 'vehicle-relative lateral view of highway boundary and sidewalk inventory',
     'location_xyz_m': [-4, 2, 1.3], 'rotation_pyr_deg': [0, -25, 0]},
    {'name': 'driver_reference', 'width': 1280, 'height': 720, 'fps': 20, 'fov_deg': 95,
     'pose_strategy': 'vehicle-relative rear view for traffic direction and context',
     'location_xyz_m': [-7, 0, 2], 'rotation_pyr_deg': [0, 180, 0]},
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    source = Path(__file__).resolve().parent
    runner = (source / 'runner.py').read_text()
    meter = (source / 'walking_side.py').read_text()
    finalizer = (source / 'saved_walking.py').read_text()
    walker_adapter = (source / 'walker_capture_adapter.py').read_text()
    source_channels = (source / 'source_channels.py').read_text()
    cases = []
    for condition in ('a', 'b'):
        case_id = CASE + condition
        description = {'channels': [
                           {'name': 'kin.position', 'unit': 'm', 'sampling_rate_hz': 20,
                            'method': 'Original Native pedestrian position at each video frame',
                            'time_window': 'entire 30-second source attempt',
                            'reference_frame': 'Native map coordinates',
                            'uncertainty': '50 ms sampling; physical body and pixel review required'},
                           {'name': 'kin.speed', 'unit': 'm/s', 'sampling_rate_hz': 20,
                            'method': 'Norm of original Native pedestrian velocity',
                            'time_window': 'entire 30-second source attempt',
                            'reference_frame': 'Native map coordinates',
                            'uncertainty': '50 ms sampling; physical motion review required'}],
                       'context_inputs': [{'name': 'highway_boundary_source', 'unit': 'structured',
                                           'method': 'Reviewed Native map boundary, sidewalk and subsection 6 packet'}],
                       'limitations': ['Highway authority, sidewalk inventory and obstruction context require external source review',
                                       'No fixture proves physical motion or legal compliance']}
        for name, unit in (('ru.subject', 'structured'), ('st.sidewalk', 'structured'),
                           ('st.highway', 'structured'), ('rel.occupies', 'structured'),
                           ('kin.heading', 'deg'), ('st.lane_direction', 'structured'),
                           ('rel.oncoming', 'structured')):
            description['channels'].append({'name': name, 'unit': unit, 'sampling_rate_hz': 20,
                'method': 'Original pedestrian and vehicle trace joined to the reviewed highway source packet; no legal verdict',
                'time_window': 'entire 30-second source attempt',
                'reference_frame': 'Native map coordinates and original video frames',
                'uncertainty': '50 ms sampling; original map, body and pixel review required'})
        config = {'case_id': case_id, 'selected_case_id': case_id,
                  'selected_case_ids': [CASE + 'a', CASE + 'b'],
                  'supported_case_ids': [CASE + 'a', CASE + 'b'],
                  'law_id': 'NRS-484B-297-2', 'cell_id': 'C230259', 'actor': 'pedestrian',
                  'case': {'case_id': case_id, 'recording_description': description},
                  'condition': condition, 'rate_hz': 20,
                  'duration_s': 30, 'frames': 600, 'source_packet_required': True,
                  'source_packets': [], 'required_atoms': ['kin.position', 'kin.speed'],
                  'cameras': CAMERAS, 'recording_description': description,
                  'requested_speed_mps': .4,
                  'walker_spawn_height_adjustment_m': 0.0,
                  'physical_completion': {
                      'criterion': 'travel_progress', 'motion_source': 'trace.jsonl',
                      'position_key': 'position_m', 'direction_xy': [-1, 0],
                      'minimum_progress_m': 6.0,
                      'context_sources': ['reviewed-road-source.json']},
                  'legal_verdict': None}
        test = '''import copy\nimport json\nimport unittest\nfrom pathlib import Path\nfrom runner import check, _packet\n\nclass ExactDraft(unittest.TestCase):\n def setUp(self): self.config=json.loads(Path('config.json').read_text())\n def test_contract(self):\n  receipt=check(self.config)\n  self.assertEqual(receipt['frames'],600)\n  self.assertFalse(receipt['physical_completion'])\n  self.assertFalse(receipt['carla_contacted'])\n def test_negative(self):\n  for key,value in [('frames',599),('actor','driver'),('physical_completion',True),('source_packet_required',False)]:\n   bad=copy.deepcopy(self.config);bad[key]=value\n   with self.assertRaises(ValueError):check(bad)\n def test_no_unsourced_native(self):\n  with self.assertRaises(FileNotFoundError):_packet('missing-original-source.json',self.config)\n'''
        construction = {'case_id': case_id, 'cell_id': 'C230259', 'law_id': 'NRS-484B-297-2',
                        'actor': 'pedestrian', 'status': 'draft', 'entrypoint': 'runner.py',
                        'files': [{'path': 'runner.py', 'content': runner},
                                  {'path': 'walking_side.py', 'content': meter},
                                  {'path': 'saved_walking.py', 'content': finalizer},
                                  {'path': 'walker_capture_adapter.py', 'content': walker_adapter},
                                  {'path': 'source_channels.py', 'content': source_channels},
                                  {'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
                                  {'path': 'tests/test_offline.py', 'content': test}],
                        'recording_description': description,
                        'measurement_plan': {'sources': ['reviewed-road-source.json',
                                                          'walking-source.jsonl', 'video_frames.jsonl',
                                                          'trace.jsonl'] +
                                                         ['channels/' + item['name'] + '.jsonl'
                                                          for item in description['channels']],
                                             'saved_finalizer': 'saved_walking.py',
                                             'continuous_window_frames': 600,
                                             'legal_verdict': None},
                        'static_checks': [{'name': 'exact_source_packet_and_camera_plan',
                                           'command': 'runner.py --check', 'status': 'passed_offline'}],
                        'termination_rules': {'full_window_frames': 600,
                                              'stop_on_missing_original_source': True,
                                              'retain_failure_evidence': True},
                        'mechanisms': {'construction_status': 'draft_executable',
                                       'pedestrian_control': 'Native WalkerControl with reviewed opposite traffic heading',
                                       'vehicle_control': 'separate Native vehicle on reviewed approach route',
                                       'camera_capture': 'four synchronized Native RGB streams encoded FFV1',
                                       'world_cleanup': 'owned actors destroyed and world restored with readback'}}
        path = BASE / 'draft-native' / condition / 'construction.json'
        write(path, construction)
        cases.append({'case_id': case_id, 'construction': str(path.relative_to(BASE)),
                      'construction_sha256': digest(path), 'candidates': [],
                      'candidate_risk': {'status': 'physical',
                                         'reason': 'Native highway boundary, sidewalk absence, pedestrian route and camera visibility require source review; fallback not yet built.'}})
    write(BASE / 'draft-native-manifest.json',
          {'format': 'worker-unselected-draft-construction-manifest-v1',
           'assignment_id': BASE.name, 'status': 'draft_not_selected', 'cases': cases,
           'original_native_observed': False, 'delivery_ready': False})


if __name__ == '__main__':
    main()
