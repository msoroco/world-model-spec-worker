"""Build exact selected parked-headlamp constructions and canonical root files."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SIZES = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))
MODULES = ('lamp_probe.py', 'parking_geometry.py', 'native_capture.py',
           'camera_recorder.py', 'saved_lamps.py', 'delivery_audit.py',
           'comparison_audit.py', 'owned_capture.py', 'acquisition_finalizer.py',
           'lamp_photometry.py', 'analysis.py', 'native_publication.py',
           'parking_completion.py')
TEST = '''import os
import unittest
from unittest.mock import patch
import runner


class SelectedBundleTests(unittest.TestCase):
    def test_exact_selected_identity(self):
        self.assertTrue(runner.check().startswith('testing__C110454__NRS-484D-165-4__motor_vehicle_driver__'))

    def test_refuses_unreviewed_site(self):
        with patch.dict(os.environ, {'PARKED_HEADLAMP_SITE_PACKET': ''}), \\
             patch('sys.argv', ['runner.py', '--output-dir', 'attempt']):
            with self.assertRaisesRegex(ValueError, 'SITE_PACKET'):
                runner.main()


if __name__ == '__main__':
    unittest.main()
'''


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def description() -> dict:
    methods = {
        'original_actor_state': 'Original vehicle identity, speed, handbrake, body footprint and lamp readback',
        'original_four_view_frame_map': 'Original four-camera frames joined to Native world tick',
        'headlamp_emission_and_aim_review': 'Original camera images and reviewed fixed lamp-region pixels; physical/legal review retained',
    }
    return {'channels': [{'name': name, 'unit': 'structured record',
                         'sampling_rate_hz': 20, 'method': method,
                         'time_window': 'complete 45-second stationary interval',
                         'reference_frame': 'original Native frame and world time',
                         'uncertainty': '20 Hz sample spacing, camera image and surveyed polygon precision'}
                        for name, method in methods.items()],
            'context_inputs': [{'name': 'reviewed_site_geometry', 'unit': 'structured record',
                                'method': 'Source-hashed reviewed map, parking and intersection geometry'}],
            'limitations': ['API lamp bits do not establish emitted intensity or beam aim.',
                            'Pixel contrast does not establish statutory depressed or dimmed meaning.']}


def build() -> None:
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    plan['source_observation_mapping'] = {}
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 45,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'parked body, intersection boundary and approach', 'interval': 'all 900 frames'},
            {'view': 'approach', 'subject': 'original headlamp emission and road-surface beam', 'interval': 'all 900 frames'},
            {'view': 'reference_corner', 'subject': 'reviewed parking polygon and vehicle body footprint', 'interval': 'all 900 frames'},
            {'view': 'driver_reference', 'subject': 'headlamp aim relative to reviewed camera pose', 'interval': 'all 900 frames'},
        ]}
    write_json(plan_path, plan)
    plan_hash = sha(plan_path)
    proposal_path = HERE / 'proposals' / 'cases.json'
    proposal = json.loads(proposal_path.read_text(encoding='utf-8'))
    recording = description()
    for item in proposal['cases']:
        item['recording_description'] = recording
    write_json(proposal_path, proposal)
    selected = []
    for case in plan['cases']:
        case_id = case['case_id']
        mode = case['requested_headlamp_mode']
        if case_id != ASSIGNMENT + '__' + mode:
            raise ValueError('selected exact parked-headlamp identity differs')
        config = {
            'assignment_id': ASSIGNMENT, 'law_id': 'NRS-484D-165-4',
            'cell_id': 'C110454', 'actor': 'motor_vehicle_driver',
            'selected_case_id': case_id, 'supported_case_ids': [row['case_id'] for row in plan['cases']],
            'requested_headlamp_mode': mode, 'plan_sha256': plan_hash,
            'camera_pose_source': 'primary',
            'rate_hz': 20, 'frame_count': 900, 'duration_s': 45,
            'cameras': [{'name': view, 'width': size[0], 'height': size[1],
                         'pose_strategy': 'source-reviewed site-relative four-view pose',
                         'fov_deg': 70 if view == 'overview' else 45}
                        for view, size in zip(VIEWS, SIZES)],
            'camera_dimensions': {view: list(size) for view, size in zip(VIEWS, SIZES)},
            'source_requirements': ['reviewed_site', 'actor_state', 'camera_frame_map',
                                    'original_camera_media', 'reviewed_lamp_roi'],
            'required_atoms': [], 'source_packets': [], 'diagnostic_only': False,
            'case': {'case_id': case_id, 'recording_description': recording},
        }
        files = [(name, (HERE / name).read_text(encoding='utf-8')) for name in MODULES]
        files.extend([('runner.py', (HERE / 'selected_runner.py').read_text(encoding='utf-8')),
                      ('config.json', json.dumps(config, indent=2, sort_keys=True) + '\n'),
                      ('case-plan.json', plan_path.read_text(encoding='utf-8')),
                      ('tests/test_bundle.py', TEST)])
        construction = {'law_id': 'NRS-484D-165-4', 'cell_id': 'C110454',
                        'actor': 'motor_vehicle_driver', 'case_id': case_id,
                        'entrypoint': 'runner.py', 'diagnostic_only': False,
                        'recording_description': recording,
                        'files': [{'path': name, 'content': content} for name, content in files]}
        path = HERE / ('construction-' + mode + '.json')
        write_json(path, construction)
        selected.append((case_id, mode, path, config, construction))
        fallback_config = dict(config, camera_pose_source='fallback1')
        fallback = copy.deepcopy(construction)
        for item in fallback['files']:
            if item['path'] == 'config.json':
                item['content'] = json.dumps(fallback_config, indent=2, sort_keys=True) + '\n'
        write_json(HERE / ('construction-fallback1-' + mode + '.json'), fallback)
    root_id, _, _, config, construction = selected[0]
    (HERE / 'runner.py').write_text((HERE / 'selected_runner.py').read_text(encoding='utf-8'),
                                    encoding='utf-8')
    write_json(HERE / 'config.json', config)
    construction.update({
        'measurement_plan': {'source': 'source-hashed original actor, four-view and lamp ROI observations',
                             'finalizer': 'analysis.py'},
        'static_checks': ['exact 900-frame case and mode', 'four source-joined camera archives'],
        'termination_rules': ['45 seconds at 20 Hz', 'fail on source gaps or restoration failure'],
        'mechanisms': ['reviewed site packet', 'stationary handbrake', 'exact headlamp-mode command',
                       'four original camera sensors', 'Core capture tick hook'],
    })
    write_json(HERE / 'construction.json', construction)
    write_json(HERE / 'execution-manifest.draft.json', {
        'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
        'runtime_manifest_sha256': sha(HERE.parents[1] / 'runtime' / 'SOURCE-MANIFEST.json'),
        'status': 'selected_cpu_proofs_in_progress',
        'cases': [{'case_id': case_id, 'kind': 'delivery',
                   'construction': path.name, 'construction_sha256': sha(path),
                   'candidate_risk': {'status': 'physical',
                                      'reason': 'Original lamp emission or aim may not be visible from the primary surveyed camera pose.'},
                   'candidates': [{'id': 'fallback1',
                        'construction': 'construction-fallback1-' + mode + '.json',
                        'construction_sha256': sha(HERE / ('construction-fallback1-' + mode + '.json')),
                        'trigger': {'source': 'source-joined original approach and driver-reference camera pixels',
                                    'metric': 'independent headlamp and road-surface beam pixel resolvability',
                                    'failure_condition': 'primary camera images cannot resolve headlamp and road-surface beam in the fixed reviewed ROIs'},
                        'changed_knobs': ['camera pose source: alternate_camera_poses in source-sealed site packet']}]}
                  for case_id, mode, path, _, _ in selected]})
    print('selected', len(selected), 'parked-headlamp constructions; root', root_id)


if __name__ == '__main__':
    build()
