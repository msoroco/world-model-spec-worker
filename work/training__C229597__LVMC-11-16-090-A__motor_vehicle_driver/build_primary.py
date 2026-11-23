"""Build two C229597 draft cases and three alternatives for each."""
import copy
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent
CASE = 'training__C229597__LVMC-11-16-090-A__motor_vehicle_driver__reference'
ASSIGNMENT = CASE.rsplit('__', 1)[0]
SPAWNS = {'primary': 0, 'fallback1': 1, 'fallback2': 2, 'fallback3': 3}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


config = {
    'case_id': CASE, 'selected_case_id': CASE, 'cell_id': 'C229597',
    'law_id': 'LVMC-11-16-090-A', 'actor': 'motor_vehicle_driver',
    'case': {'case_id': CASE, 'name': 'reference'}, 'candidate_id': 'primary', 'spawn_point_index': 0,
    'duration_s': 30, 'rate_hz': 20,
    'vehicle_blueprint': 'vehicle.tesla.model3',
    'required_atoms': ['kin.speed', 'kin.accel_longitudinal', 'kin.position'],
    'source_packets': [],
    'cameras': [{'name': name, 'width': 1920 if name == 'overview' else 1280,
                 'height': 1080 if name == 'overview' else 720, 'fov_deg': 90}
                for name in ('overview', 'approach', 'reference_corner',
                             'driver_reference')],
    'control_phases': [
        {'name': 'approach', 'first_frame': 0, 'last_frame': 159,
         'throttle': 0.28, 'steer': 0.0, 'brake': 0.0},
        {'name': 'acceleration', 'first_frame': 160, 'last_frame': 319,
         'throttle': 0.75, 'steer': 0.0, 'brake': 0.0},
        {'name': 'peak', 'first_frame': 320, 'last_frame': 439,
         'throttle': 0.92, 'steer': 0.0, 'brake': 0.0},
        {'name': 'departure', 'first_frame': 440, 'last_frame': 599,
         'throttle': 0.20, 'steer': 0.0, 'brake': 0.0},
    ],
}
test = '''import json
import unittest
from pathlib import Path
from runner import FRAMES, HZ, check, phase_at
from measure_episode import derive


class ExactCaptureContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_full_duration_and_boundaries(self):
        receipt = check(self.config)
        self.assertEqual((receipt['frames'], receipt['rate_hz']), (600, 20))
        self.assertEqual([phase_at(self.config, frame)['name'] for frame in
                          (0, 159, 160, 319, 320, 439, 440, 599)],
                         ['approach', 'approach', 'acceleration', 'acceleration',
                          'peak', 'peak', 'departure', 'departure'])
        self.assertEqual(len([phase_at(self.config, frame) for frame in
                              range(FRAMES)]), FRAMES)

    def test_exact_identity_and_camera_rejection(self):
        changed = dict(self.config, case_id=self.config['case_id'] + '-wrong')
        with self.assertRaises(ValueError):
            check(changed)
        changed = dict(self.config, cameras=self.config['cameras'][:3])
        with self.assertRaises(ValueError):
            check(changed)
        changed = dict(self.config, spawn_point_index=8)
        with self.assertRaises(ValueError):
            check(changed)

    def test_short_or_truncated_phase_rejection(self):
        changed = dict(self.config, duration_s=10)
        with self.assertRaises(ValueError):
            check(changed)
        phases = [dict(phase) for phase in self.config['control_phases']]
        phases[-1]['last_frame'] = 598
        with self.assertRaises(ValueError):
            check(dict(self.config, control_phases=phases))

    def test_source_motion_join_and_negative(self):
        trace = [{'frame': i + 1000, 'video_frame': i, 'time_s': i / HZ,
                  'position_m': [i * .2, 0, 0],
                  'velocity_mps': [4 + i / 100, 0, 0],
                  'acceleration_mps2': [.2, 0, 0]} for i in range(FRAMES)]
        mapping = [{'video_frame': i, 'carla_frame': i + 1000,
                    'time_s': i / HZ} for i in range(FRAMES)]
        summary = derive(trace, mapping)
        self.assertEqual(summary['frames'], 600)
        self.assertAlmostEqual(summary['maximum_speed_mps'], 9.99)
        mapping[-1] = dict(mapping[-1], carla_frame=9999)
        with self.assertRaisesRegex(ValueError, 'join differs'):
            derive(trace, mapping)
'''
construction = {
    'actor': 'motor_vehicle_driver', 'case_id': CASE, 'cell_id': 'C229597',
    'law_id': 'LVMC-11-16-090-A', 'entrypoint': 'runner.py',
    'files': [
        {'path': 'runner.py', 'content': (P / 'native_runner.py').read_text()},
        {'path': 'measure_episode.py', 'content': (P / 'measure_episode.py').read_text()},
        {'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
        {'path': 'tests/test_offline.py', 'content': test},
    ],
    'measurement_plan': ('Retain original Native position, velocity and acceleration '
                         'over all 600 frames and four camera streams. Independently '
                         'review jurisdiction, highway status, motor-vehicle identity, '
                         'episode context and exhibition characterization.'),
    'mechanisms': ['20 Hz synchronous Native capture for 30 seconds',
                   'controlled approach, acceleration, peak and departure',
                   'four source RGB cameras and original velocity vectors'],
    'recording_description': {
        'channels': [
            {'name': 'ego_speed', 'unit': 'm/s', 'sampling_rate_hz': 20,
             'method': 'magnitude of original Native velocity vector',
             'time_window': 'all 600 frames', 'reference_frame': 'Native world',
             'uncertainty': '20 Hz frame bracket'},
            {'name': 'ego_acceleration', 'unit': 'm/s2', 'sampling_rate_hz': 20,
             'method': 'original Native acceleration vector',
             'time_window': 'all 600 frames', 'reference_frame': 'Native world',
             'uncertainty': '20 Hz frame bracket'},
        ],
        'context_inputs': [],
        'limitations': ['No numeric legal threshold or intent is inferred from throttle'],
    },
    'static_checks': ['exact case', '600 frames at 20 Hz',
                      'four source cameras', 'four controller phases'],
    'status': 'draft_cpu_offline_only',
    'termination_rules': ['600 synchronized Native frames or explicit failure'],
}
entries = []
for case in ('reference', 'contrast'):
    variants = []
    for candidate, spawn in SPAWNS.items():
        cfg = copy.deepcopy(config)
        cfg['case_id'] = ASSIGNMENT + '__' + case
        cfg['selected_case_id'] = cfg['case_id']
        cfg['case'] = {'case_id': cfg['case_id'], 'name': case}
        cfg['candidate_id'] = candidate
        cfg['spawn_point_index'] = spawn
        if case == 'contrast':
            cfg['control_phases'][1]['throttle'] = 0.28
            cfg['control_phases'][2]['throttle'] = 0.28
        proposal = copy.deepcopy(construction)
        proposal['case_id'] = cfg['case_id']
        next(item for item in proposal['files'] if item['path'] == 'config.json')['content'] = json.dumps(cfg, indent=2) + '\n'
        rel = f'draft-primary/{case}/{candidate}/construction.json'
        target = P / rel
        write(target, proposal)
        if candidate == 'primary':
            primary = {'construction': rel, 'construction_sha256': sha(target)}
        else:
            variants.append({'id': candidate, 'construction': rel,
                             'construction_sha256': sha(target),
                             'changed_knobs': ['spawn_point_index'],
                             'trigger': {'source': 'original Native route review',
                                         'metric': 'spawn availability and route geometry',
                                         'failure_condition': 'Primary spawn occupied or route unusable'}})
    entries.append({'case_id': ASSIGNMENT + '__' + case, 'kind': 'delivery',
                    **primary, 'candidates': variants,
                    'measurement_procedure': {'entrypoint': 'measure_episode.py',
                                              'output_schema': 'c229597-source-motion-analysis-v1'},
                    'acquisition': {
                        'kin.speed': {'entrypoint': 'measure_episode.py',
                                      'evidence': 'trace.jsonl, video_frames.jsonl',
                                      'method': 'magnitude of original Native velocity vector'},
                        'kin.accel_longitudinal': {'entrypoint': 'measure_episode.py',
                                                   'evidence': 'trace.jsonl, video_frames.jsonl',
                                                   'method': 'source-joined original acceleration vector'},
                        'kin.position': {'entrypoint': 'runner.py',
                                         'evidence': 'trace.jsonl, video_frames.jsonl',
                                         'method': 'retain original Native position and frame identity'},
                        'ego_speed': {'entrypoint': 'measure_episode.py',
                                      'evidence': 'trace.jsonl, video_frames.jsonl',
                                      'method': 'derive speed channel from original velocity vectors'},
                        'ego_acceleration': {'entrypoint': 'measure_episode.py',
                                             'evidence': 'trace.jsonl, video_frames.jsonl',
                                             'method': 'derive acceleration channel from original vectors'},
                    },
                    'candidate_risk': {'status': 'physical',
                                       'reason': 'Spawn, route and camera framing need Native review'}})
manifest = {'assignment_id': ASSIGNMENT, 'format': 'worker-execution-manifest',
            'status': 'draft_cpu_offline_only', 'cases': entries}
write(P / 'draft-primary-manifest.json', manifest)
print(json.dumps({'cases': len(entries), 'candidate_constructions': 8,
                  'manifest_sha256': sha(P / 'draft-primary-manifest.json')}))
