"""Materialize source-bound exact offline bundles for four straight-green cases."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
SUFFIXES = ('green_clear', 'green_vehicle_present', 'green_pedestrian_present', 'green_pedestrian_late')
ALL = [AID + '__' + suffix for suffix in SUFFIXES]
MODULES = ('runner.py', 'analysis.py', 'native_scene.py', 'straight_control.py', 'native_capture.py',
           'original_camera_recorder.py', 'native_session.py', 'saved_attempt.py',
           'delivery_audit.py', 'comparison_audit.py', 'tests/test_offline_case.py')


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + '\n')


def scene(suffix):
    kind, region = { 'green_clear': (None, None), 'green_vehicle_present': ('motor_vehicle', 'intersection'),
                     'green_pedestrian_present': ('pedestrian', 'adjacent_crosswalk'),
                     'green_pedestrian_late': ('pedestrian', 'outside')}[suffix]
    point = {'green_clear': None, 'green_vehicle_present': [0, 0],
             'green_pedestrian_present': [0, 2.5], 'green_pedestrian_late': [0, 4]}[suffix]
    return {'assignment_id': AID, 'case_id': AID + '__' + suffix, 'case_suffix': suffix,
            'law_id': 'NRS-484B-307-2a', 'cell_id': 'C111125', 'actor': 'motor_vehicle_driver',
            'route_xy': [[-20, 0], [0, 0], [20, 0]], 'straight_tolerance_m': 0.2,
            'intersection_polygon_xy': [[-3, -3], [3, -3], [3, 1], [-3, 1]],
            'adjacent_crosswalk_polygon_xy': [[-3, 2], [3, 2], [3, 3], [-3, 3]],
            'official_signal_aspects': ['circular_green'], 'other_user_kind': kind,
            'other_user_region_at_exhibition': region,
            'other_user_spawn_xy': point, 'other_user_destination_xy': [0, 2.5] if suffix == 'green_pedestrian_late' else None,
            'rate_hz': 20, 'duration_frames': 900}


def recording():
    names = ('official_signal_history', 'ego_body_history', 'other_user_history',
             'intersection_geometry', 'adjacent_crosswalk_geometry', 'camera_frame_map')
    return {'channels': [{'name': name, 'unit': 'original structured record', 'sampling_rate_hz': 20,
                          'method': 'Source-hashed original Native event, site and frame-map acquisition',
                          'time_window': '30 s original circular-green exhibition and crossing',
                          'reference_frame': 'Native world, original frame and elapsed time',
                          'uncertainty': '20 Hz temporal and Native map/body precision'} for name in names],
            'context_inputs': [{'name': 'official_signal_and_device_context', 'unit': 'original source packet',
                                'method': 'Original site survey, official head and other-device inventory'},
                               {'name': 'participant_lawful_presence_context', 'unit': 'original source packet',
                                'method': 'Source-sealed participant identity and lawful-presence review context'}],
            'limitations': ['Physical visibility, motion and lawful presence need independent original review.',
                            'Engineering hold policy is not a legal right-of-way verdict.']}


def build():
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
                'runtime_manifest_sha256': hashlib.sha256((REPO / 'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest(),
                'cases': []}
    rec = recording()
    for suffix in SUFFIXES:
        item = scene(suffix)
        cid = item['case_id']
        cfg = {'assignment_id': AID, 'selected_case_id': cid, 'supported_case_ids': ALL,
               'law_id': item['law_id'], 'cell_id': item['cell_id'], 'actor': item['actor'],
               'rate_hz': 20, 'duration_s': 45, 'required_atoms': [], 'source_packets': [],
               'cameras': [dict(name=name, width=width, height=height,
                                pose_strategy='source-surveyed Native camera pose', fov_deg=90)
                           for name, width, height in [('overview', 1920, 1080), ('approach', 1280, 720),
                                                       ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]],
               'case': {'case_id': cid, 'scenario_parameters': item,
                        'recording_description': rec},
               'physical_completion': {'criterion': 'travel_progress', 'motion_source': 'trace.jsonl',
                                       'position_key': 'position_m', 'minimum_progress_m': 5,
                                       'minimum_samples': 2, 'engineering_tolerances_not_legal': True}}
        # This family is 900 frames at 20 Hz, hence 45 s.
        entries = []
        for rel in MODULES:
            entries.append({'path': rel, 'source': 'work/' + AID + '/' + rel,
                            'content': (ROOT / rel).read_text()})
        entries.append({'path': 'scene.json', 'content': json.dumps(item, sort_keys=True, indent=2) + '\n'})
        entries.append({'path': 'config.json', 'content': json.dumps(cfg, sort_keys=True, indent=2) + '\n'})
        construction = {'law_id': item['law_id'], 'cell_id': item['cell_id'], 'actor': item['actor'],
                        'case_id': cid, 'entrypoint': 'runner.py', 'files': entries,
                        'recording_description': rec,
                        'measurement_plan': {'green_exhibition': 'Original official head and other-user region at exhibition',
                                             'crossing': 'Original ego body in surveyed intersection with unresolved legal verdict'},
                        'mechanisms': ['source-verified official circular-green head and straight map route',
                                       'case-specific other-user placement and independent original media capture'],
                        'static_checks': ['straight route crosses surveyed intersection',
                                          'other user spawns in exact exhibition region'],
                        'termination_rules': ['stop after 900 original ticks or failed source/readback']}
        relative = 'construction.json' if suffix == SUFFIXES[0] else 'cases/' + suffix + '/construction.json'
        write(ROOT / relative, construction)
        if suffix == SUFFIXES[0]:
            write(ROOT / 'config.json', cfg)
            write(ROOT / 'scene.json', item)
        digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        manifest['cases'].append({'case_id': cid, 'kind': 'delivery', 'construction': relative,
                                  'construction_sha256': digest,
                                  'measurement_contract': 'measurement-' + suffix + '.json',
                                  'measurement_procedure': {'entrypoint': 'analysis.py'},
                                  'fixture_recipe': 'work/' + AID + '/diagnostic-' + suffix + '-recipe.json',
                                  'native_handoff': {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST',
                                                     'port_env_var': 'CARLA_PORT'},
                                  'candidate_risk': {'status': 'physical', 'reason': 'Original phase and participant visibility may fail on a surveyed Native map.'},
                                  'candidates': []})
    write(ROOT / 'execution-manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps({'cases': len(build()['cases'])}))
