"""Build exact six-case Native construction candidates for CPU offline checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from selected_plan import AID, CASES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


CAMERAS = [
    {'name': 'overview', 'width': 1920, 'height': 1080, 'fps': 20,
     'fov_deg': 90, 'pose_strategy': 'world_static',
     'location_xyz_m': [18, -18, 30], 'rotation_pyr_deg': [-42, 0, 145]},
    {'name': 'approach', 'width': 1280, 'height': 720, 'fps': 20,
     'fov_deg': 85, 'pose_strategy': 'world_static',
     'location_xyz_m': [4, -24, 7], 'rotation_pyr_deg': [-15, 0, 90]},
    {'name': 'reference_corner', 'width': 1280, 'height': 720, 'fps': 20,
     'fov_deg': 80, 'pose_strategy': 'world_static',
     'location_xyz_m': [11, 10, 8], 'rotation_pyr_deg': [-18, 0, 230]},
    {'name': 'driver_reference', 'width': 1280, 'height': 720, 'fps': 20,
     'fov_deg': 85, 'pose_strategy': 'ego_follow',
     'location_xyz_m': [1, 0, 1.5], 'rotation_pyr_deg': [0, 0, 0]},
]
CHANNELS = [
    {'name': name, 'unit': unit, 'sampling_rate_hz': 20,
     'method': 'Original Native frame joined to four camera frames and source geometry',
     'time_window': '600 frames / 30 seconds',
     'reference_frame': 'original Native frame and time',
     'uncertainty': 'Actual standing/parking purpose and Chapter exceptions need independent source review'}
    for name, unit in (
        ('native_pose_extract', 'frame,time_s,m,deg,m/s'),
        ('road_edge_tangent', 'unit vector'),
        ('lawful_traffic_direction', 'unit vector'),
        ('edge_parallel_angle_deg', 'degree'),
        ('lawful_traffic_heading_angle_deg', 'degree'),
        ('kin.heading', 'degree'), ('kin.speed', 'm/s'),
        ('drv.standing_or_parked', 'source review'),
        ('st.roadway', 'road geometry'), ('st.road_edge', 'road geometry'),
        ('st.lane_direction', 'road geometry'), ('rel.occupies', 'body history'),
        ('st.parking_space', 'permission context'))]
DESCRIPTION = {'channels': CHANNELS,
    'context_inputs': [
        {'name': 'road_edge_survey', 'unit': 'source-hashed Native survey',
         'method': 'Native map/road/lane/body identity with pending independent authority review'},
        {'name': 'activity_context', 'unit': 'source review',
         'method': 'Original full video and purpose review; requested activity is not proof'}],
    'limitations': ['No legal conclusion from authored geometry or synthetic fixtures',
                    'Chapter exception and actual standing/parking purpose require independent review']}

TEST = '''import copy\nimport json\nimport unittest\nfrom pathlib import Path\nfrom roadside_scene import check\n\nclass ExactRoadEdge(unittest.TestCase):\n def setUp(self):\n  self.config=json.loads(Path('config.json').read_text())\n  self.road=Path('road-edge-road.xodr').read_text()\n def test_exact(self):\n  result=check(self.config,self.road)\n  self.assertEqual(result['frames'],600)\n  self.assertFalse(result['original_native_observed'])\n def test_short(self):\n  cfg=copy.deepcopy(self.config);cfg['duration_frames']=599\n  with self.assertRaises(ValueError):check(cfg,self.road)\n def test_crosses_edge(self):\n  cfg=copy.deepcopy(self.config);cfg['requested_rest_center_x_m']=6.8\n  with self.assertRaises(ValueError):check(cfg,self.road)\n'''


def main():
    files = ['runner.py', 'capture.py', 'cameras.py', 'activity.py', 'roadside_scene.py',
             'selected_plan.py', 'road-edge-road.xodr', 'source_audit.py']
    cases = []
    for case, setting in CASES.items():
        variants = []
        for candidate, mode in (('primary', 'service_brake'),
                                ('fallback1', 'service_and_hand_brake')):
            config = {'case_id': case, 'selected_case_id': case,
                'law_id': 'LVMC-11-52-040-A', 'cell_id': 'C229351',
                'actor': 'motor_vehicle_driver', 'layout': 'road',
                'maneuver': 'parallel_park', 'control': 'road_edge',
                'activity_requested': setting['activity'],
                'rest_pose_requested': setting['pose'],
                'requested_yaw_offset_deg': setting['requested_yaw_offset_deg'],
                'requested_rest_center_x_m': 4.2,
                'controller_mode': mode,
                'duration_s': 30, 'rate_hz': 20, 'duration_frames': 600,
                'required_atoms': ['kin.heading', 'kin.speed'],
                'source_packets': [], 'cameras': CAMERAS,
                'supported_case_ids': list(CASES),
                'physical_completion': {}, 'legal_verdict': None,
                'recording_description': DESCRIPTION,
                'case': {'case_id': case, 'recording_description': DESCRIPTION}}
            content = [{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
                       {'path': 'tests/test_offline.py', 'content': TEST}]
            content += [{'path': name, 'content': (HERE / name).read_text()} for name in files]
            construction = {'format': 'worker-inline-construction',
                'case_id': case, 'law_id': 'LVMC-11-52-040-A',
                'cell_id': 'C229351', 'actor': 'motor_vehicle_driver',
                'entrypoint': 'runner.py', 'files': content,
                'measurement_plan': 'source-audited at-rest yaw, edge angle and activity context',
                'recording_description': DESCRIPTION,
                'static_checks': ['six-case scope', 'authored roadway body footprint', 'four-view profile'],
                'termination_rules': ['600 synchronized 20-Hz frames or retained error'],
                'mechanisms': ['one-way roadway edge', 'braked resting motor vehicle'],
                'original_native_observed': False}
            path = HERE / f"condition_{setting['activity']}_{setting['pose']}-{candidate}.json"
            write(path, construction)
            variants.append({'id': candidate, 'construction': path.name,
                             'construction_sha256': sha(path)})
        cases.append({'case_id': case,
            'construction': variants[0]['construction'],
            'construction_sha256': variants[0]['construction_sha256'],
            'candidate_risk': {'status': 'physical',
                'reason': 'Original at-rest vehicle motion and camera/body containment require Native review'},
            'candidates': [variants[1]],
            'original_native_observed': False})
    write(HERE / 'draft-manifest.json', {
        'format': 'worker-unselected-draft-construction-manifest-v1',
        'assignment_id': AID, 'status': 'draft_not_selected',
        'cases': cases, 'original_native_observed': False,
        'delivery_ready': False})
    print(json.dumps({'cases': len(cases), 'construction_candidates': len(cases) * 2,
                      'draft_manifest_sha256': sha(HERE / 'draft-manifest.json')}, sort_keys=True))


if __name__ == '__main__':
    main()
