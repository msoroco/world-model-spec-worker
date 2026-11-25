"""Materialize exact selected Native bundle drafts from one implementation."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES = [item['case_id'] for item in json.loads((ROOT / 'case-plan.json').read_text())['cases']]
NAMES = ('dev.traffic_signal', 'dev.inoperative', 'st.lane_enters',
         'st.stop_line', 'st.crosswalk', 'st.sight_distance', 'rel.visible',
         'drv.stopped', 'drv.entering_intersection', 'drv.arrival_order',
         'drv.in_intersection', 'drv.yields_to', 'kin.velocity')
CHANNELS = [{'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
             'method': 'original Native actor, surveyed map, source camera and frame join',
             'time_window': '30 s / 600 joined frames',
             'reference_frame': 'Native map and original frame',
             'uncertainty': '50 ms sample; physical visibility pending'} for name in NAMES]
DESCRIPTION = {'channels': CHANNELS, 'context_inputs': [],
               'limitations': ['Synthetic CPU proof is not observed CARLA behavior, '
                               'physical signal visibility or legal verdict']}
CAMERAS = [dict(name=name, width=width, height=height,
                pose_strategy='fixed surveyed intersection world camera',
                fov_deg=fov, xyz_m=[x, y, z], pitch_deg=pitch)
           for name, width, height, x, y, z, pitch, fov in
           (('overview', 1920, 1080, 0, -28, 28, -55, 85),
            ('approach', 1280, 720, -30, -15, 12, -25, 80),
            ('reference_corner', 1280, 720, -12, -9, 8, -35, 75),
            ('driver_reference', 1280, 720, -7, 0, 2, 0, 90))]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build(index):
    case = CASES[index]
    folder = ROOT if index == 0 else ROOT / 'cases' / 'condition_b'
    folder.mkdir(parents=True, exist_ok=True)
    config = {'case_id': case, 'selected_case_id': case, 'supported_case_ids': CASES,
              'case': {'case_id': case, 'recording_description': DESCRIPTION},
              'case_suffix': f'condition_{"a" if index == 0 else "b"}',
              'candidate_id': 'primary', 'cell_id': 'C111277',
              'law_id': 'NRS-484B-250-4', 'actor': 'motor_vehicle_driver',
              'duration_s': 30, 'rate_hz': 20,
              'required_atoms': ['st.sight_distance', 'rel.visible'],
              'source_packets': [],
              'mandatory_channels': list(NAMES), 'recording_description': DESCRIPTION,
              'cameras': CAMERAS,
              'physical_completion': {'criterion': 'intersection_clearance',
                                      'motion_source': 'interaction_history.jsonl',
                                      'body_key': 'states.ego.body_vertices_m',
                                      'context_sources': ['signal_context.json'],
                                      'exit_axis': 0, 'exit_sign': 1}}
    write(folder / 'config.json', config)
    for name in ('runner.py', 'controller.py', 'scene.py', 'finalize.py',
                 'finalize_source.py', 'measure.py'):
        (folder / name).write_text((ROOT / 'native' / name).read_text())
    test = folder / 'tests' / 'test_scene.py'
    test.parent.mkdir(parents=True, exist_ok=True)
    test.write_text((ROOT / 'native' / 'tests' / 'test_scene.py').read_text())
    files = []
    for name in ('runner.py', 'controller.py', 'scene.py', 'finalize.py',
                 'finalize_source.py', 'measure.py', 'tests/test_scene.py', 'config.json'):
        files.append({'path': name, 'content': (folder / name).read_text()})
    construction = {'case_id': case, 'cell_id': 'C111277',
                    'law_id': 'NRS-484B-250-4', 'actor': 'motor_vehicle_driver',
                    'entrypoint': 'runner.py', 'files': files,
                    'recording_description': DESCRIPTION,
                    'measurement_plan': {'method': 'original signal, map, ego and other vehicle frame joins',
                                         'status': 'CPU draft; physical realization pending'},
                    'static_checks': ['600-frame 20 Hz capture', 'four camera sources',
                                      'crosswalk and signal authored geometry'],
                    'termination_rules': ['600 original joined frames', 'restore Native world'],
                    'mechanisms': ['OpenDRIVE crosswalk and signal',
                                   'observed stop/yield controller',
                                   'four synchronized lossless cameras'],
                    'status': 'cpu_draft'}
    write(folder / 'construction.json', construction)
    dispositions = json.loads((ROOT / 'case-plan.json').read_text())['requirement_dispositions']
    definitions = (
        ('signal_and_stop_reference', 'measure_activation',
         ['geometry.json', 'signal.json', 'native-rows.jsonl']),
        ('post_stop_priority', 'measure_yield',
         ['geometry.json', 'native-rows.jsonl']),
        ('selected_crosswalk_sight', 'measure_scope', ['capture/evidence.jsonl']),
        ('duplicate_reviewed_scope', 'measure_scope_duplicate', ['capture/evidence.jsonl']))
    contract = {'format': 'worker-measurement-contract', 'case_id': case,
                'requirements': [dict(disposition_index=i,
                                      requirement=dispositions[i]['requirement'],
                                      source=dispositions[i]['source'],
                                      output_key=key, method=method,
                                      inputs=inputs, value_type='object', kind='measured')
                                 for i, (key, method, inputs) in enumerate(definitions)],
                'negative': {'remove': ['signal.json'],
                             'error_contains': 'Missing required source: signal.json'}}
    write(folder / 'measurement-contract.json', contract)
    for candidate, tuning in (
            ('fallback1', {'roll_throttle': .18, 'other_entry_speed_mps': 5.5,
                           'other_clear_speed_mps': 3.5}),
            ('fallback2', {'roll_throttle': .25, 'other_entry_speed_mps': 6.0,
                           'other_clear_speed_mps': 4.5})):
        alternate = json.loads(json.dumps(construction))
        alternate['candidate_id'] = candidate
        alternate['mechanisms'].append('source-observed motion tuning: ' + candidate)
        for item in alternate['files']:
            if item['path'] == 'config.json':
                alternate_config = json.loads(item['content'])
                alternate_config['candidate_id'] = candidate
                alternate_config['motion_tuning'] = tuning
                item['content'] = json.dumps(alternate_config, indent=2) + '\n'
        write(ROOT / 'candidates' / ('condition_a' if index == 0 else 'condition_b') /
              candidate / 'construction.json', alternate)
    return case


if __name__ == '__main__':
    print(json.dumps({'cases': [build(0), build(1)]}))
