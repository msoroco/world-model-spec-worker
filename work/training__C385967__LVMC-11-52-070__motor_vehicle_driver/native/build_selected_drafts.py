"""Create exact selected primary and control fallback CPU construction candidates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_draft import CAMERAS

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def main():
    cases = []
    cameras = [dict(item, pose_strategy='ego_follow' if item['name']=='driver_reference'
                    else 'world_static') for item in CAMERAS]
    channels = []
    for name in ('dev.regulatory_sign', 'st.parking_space', 'st.lane_marking',
                 'drv.standing_or_parked', 'kin.heading', 'st.lane_direction',
                 'rel.occupies', 'native_body_pose', 'camera_frame_join'):
        channels.append({'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
            'method': 'Original Native source joined to saved body, camera and context evidence',
            'time_window': 'all 600 frames / 30 seconds',
            'reference_frame': 'original Native frame and time',
            'uncertainty': 'City authorization, marking and actual activity require independent review'})
    description = {'duration_s': 30, 'rate_hz': 20,
        'source_cameras': [c['name'] for c in cameras], 'channels': channels,
        'context_inputs': [{'name': 'City Traffic Engineer street designation',
            'unit': 'document', 'method': 'Separate external document with SHA-256; never inferred from authored sign'}],
        'limitations': ['No legal conclusion from offline or synthetic data',
                        'City permission and actual Native parked pose require independent review']}
    test = '''import copy\nimport json\nimport unittest\nfrom pathlib import Path\nfrom selected_runner import check\nclass ExactAnglePark(unittest.TestCase):\n def setUp(self): self.c=json.loads(Path('config.json').read_text())\n def test_selected(self): self.assertEqual(check(self.c)['frames'],600)\n def test_short(self):\n  c=copy.deepcopy(self.c);c['duration_frames']=599\n  with self.assertRaises(ValueError):check(c)\n def test_missing_permission(self):\n  c=copy.deepcopy(self.c);c['permission_source_required']=False\n  with self.assertRaises(ValueError):check(c)\n def test_wrong_orientation(self):\n  c=copy.deepcopy(self.c);c['requested_front_yaw_deg']+=180\n  with self.assertRaises(ValueError):check(c)\n'''
    files = ('capture.py', 'cameras.py', 'angle_park.py', 'saved_measure.py',
             'physical_preparation.py', 'finalize.py', 'angle-bay-road.xodr')
    for suffix, yaw in (('a', 45), ('b', 225)):
        case = FOLDER.name + '__probe_' + suffix
        candidates = []
        for ident, brake in (('primary', 'hand_brake'),
                             ('fallback1', 'service_and_hand_brake')):
            config = {'case_id': case, 'selected_case_id': case,
                'law_id': 'LVMC-11-52-070', 'cell_id': 'C385967',
                'actor': 'motor_vehicle_driver', 'duration_s': 30,
                'rate_hz': 20, 'frames': 600, 'duration_frames': 600,
                'layout': 'one_way_road', 'maneuver': 'angle_park',
                'control': 'angle_parking_designation',
                'requested_front_yaw_deg': yaw,
                'parking_brake_mode': brake,
                'permission_source_required': True,
                'original_activity_source_required': True,
                'required_atoms': ['kin.heading', 'kin.speed'],
                'source_packets': [], 'cameras': cameras,
                'physical_completion': False, 'legal_verdict': None,
                'recording_description': description,
                'supported_case_ids': [FOLDER.name+'__probe_a', FOLDER.name+'__probe_b'],
                'case': {'case_id': case, 'recording_description': description}}
            content = [{'path':'config.json','content':json.dumps(config, indent=2)+'\n'},
                       {'path':'runner.py','content':(HERE/'selected_runner.py').read_text()},
                       {'path':'selected_runner.py','content':(HERE/'selected_runner.py').read_text()},
                       {'path':'tests/test_offline.py','content':test}]
            content += [{'path':name,'content':(HERE/name).read_text()} for name in files]
            construction = {'format':'worker-inline-construction',
                'case_id':case,'law_id':'LVMC-11-52-070','cell_id':'C385967',
                'actor':'motor_vehicle_driver','entrypoint':'runner.py',
                'files':content,'recording_description':description}
            path = HERE / f'condition_{suffix}-{ident}-construction.json'
            write(path, construction)
            candidates.append({'id':ident,'construction':path.name,
                               'construction_sha256':sha(path)})
        cases.append({'case_id':case,'construction':candidates[0]['construction'],
            'construction_sha256':candidates[0]['construction_sha256'],
            'candidates':candidates[1:]})
    write(HERE/'selected-draft-manifest.json',{
        'format':'worker-unselected-draft-construction-manifest-v1',
        'assignment_id':FOLDER.name,'status':'draft_not_selected',
        'cases':cases,'original_native_observed':False,'delivery_ready':False})
    print(json.dumps({'cases':len(cases),'candidates':4},sort_keys=True))


if __name__ == '__main__':
    main()
