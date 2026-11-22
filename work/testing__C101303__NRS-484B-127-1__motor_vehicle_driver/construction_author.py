"""Regenerate draft exact inline bundles; preserves frozen runtime and inputs."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
FILES = ('runner.py', 'native_capture.py', 'native_route.py',
         'native_samples.py', 'construction.py', 'following.py', 'analysis.py')
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(path, bundle_name):
    return {'path': bundle_name, 'source': str(path.relative_to(REPO)),
            'content': path.read_text()}


def recording_description():
    channels = [('ego_leader_body_speed_history', 'Original distinct actor bodies and speeds.'),
                ('traffic_condition_history', 'Original surrounding actor inventory, weather and wheel friction.'),
                ('following_lane_history', 'Original ego and leader lane/road identity by frame.'),
                ('camera_frame_map', 'Synchronized original CARLA camera frame identities.')]
    return {'channels': [{'name': name, 'unit': 'structured record',
            'sampling_rate_hz': 20, 'method': method,
            'time_window': '45 s with steady following at 14..20 s and later lane change',
            'reference_frame': 'original CARLA world frame and elapsed time',
            'uncertainty': '20 Hz sample interval and Native body/map precision'}
            for name, method in channels],
            'context_inputs': [
                {'name': 'hill_route_context', 'unit': 'structured record',
                 'method': 'Original connected Native waypoints and hill crest elevation.'},
                {'name': 'highway_context', 'unit': 'structured record',
                 'method': 'Original weather/road context; public-highway status awaits independent review.'}],
            'limitations': ['No legal reasonable-and-prudent distance cutoff.',
                            'Public-highway status and actual pixels need independent review.']}


def build():
    plan = json.loads((ROOT/'case-plan.json').read_text())
    description = recording_description()
    all_ids = [case['case_id'] for case in plan['cases']]
    previous_path = ROOT/'execution-manifest.json'
    previous = json.loads(previous_path.read_text()) if previous_path.is_file() else {}
    old_entries = {entry['case_id']: entry for entry in previous.get('cases', [])}
    entries = []
    for case in plan['cases']:
        case_id = case['case_id']
        suffix = case_id.removeprefix(ASSIGNMENT+'__')
        folder = ROOT if suffix == 'following_base_probe' else ROOT/'cases'/suffix
        scene_path = folder/'scene.json'
        scene = json.loads(scene_path.read_text())
        if scene['case_id'] != case_id:
            raise ValueError('scene identity differs from exact case')
        config = {'assignment_id': ASSIGNMENT, 'selected_case_id': case_id,
                  'supported_case_ids': all_ids, 'law_id': scene['law_id'],
                  'cell_id': scene['cell_id'], 'actor': scene['actor'],
                  'rate_hz': scene['rate_hz'], 'duration_s': scene['duration_s'],
                  'required_atoms': [], 'source_packets': [],
                  'cameras': [{'name': name, 'width': width, 'height': height,
                      'pose_strategy': 'ego mounted' if name == 'driver_reference'
                                       else 'fixed hill-following overview',
                      'fov_deg': 90} for name, width, height in CAMERAS],
                  'case': {'case_id': case_id,
                           'recording_description': description},
                  'physical_completion': {'criterion': 'travel_progress',
                      'motion_source': 'trace.jsonl', 'position_key': 'position_m',
                      'minimum_progress_m': 5, 'minimum_samples': 2,
                      'engineering_tolerances_not_legal': True}}
        config_path = folder/'config.json'
        write(config_path, config)
        files = [source(ROOT/name, name) for name in FILES]
        files += [source(scene_path, 'scene.json'),
                  source(config_path, 'config.json'),
                  source(ROOT/'tests/test_offline_case.py',
                         'tests/test_offline_case.py'),
                  source(ROOT/'tests/test_native_route.py',
                         'tests/test_native_route.py')]
        construction = {'law_id': scene['law_id'], 'cell_id': scene['cell_id'],
            'actor': scene['actor'], 'case_id': case_id, 'entrypoint': 'runner.py',
            'files': files, 'recording_description': description,
            'mechanisms': ['Native connected hill crest and adjacent forward lane',
                           'source-measured moving ego and leader gap controller',
                           'source-hashed synchronized following/lane/condition history'],
            'measurement_plan': {'following': 'Original body gap, both speeds, traffic, condition and crest crossing during 14..20 s; no legal cutoff'},
            'static_checks': ['connected hill crest with forward adjacent lane',
                              'separate moving leader and post-window lane change'],
            'termination_rules': ['stop after planned 45 s or original-source failure']}
        construction_path = folder/'construction.json'
        write(construction_path, construction)
        fallback_scene = dict(scene, route_seed_strategy='topology')
        fallback_scene_path = folder/'fallback1-scene.json'
        write(fallback_scene_path, fallback_scene)
        fallback_files = [source(fallback_scene_path, 'scene.json')
                          if item['path'] == 'scene.json' else item for item in files]
        fallback_construction = {**construction, 'files': fallback_files,
            'mechanisms': construction['mechanisms'] +
                          ['topology-seeded route search after spawn-seed failure']}
        fallback_path = folder/'fallback1-construction.json'
        write(fallback_path, fallback_construction)
        outputs = ('following_spacing_measurement', 'following_speed_measurement',
                   'following_traffic_measurement',
                   'following_highway_condition_measurement')
        contract = {'format': 'worker-measurement-contract',
            'requirements': [{'disposition_index': index,
                'requirement': disposition['requirement'],
                'source': disposition['source'], 'output_key': outputs[index],
                'method': 'measure', 'value_type': 'object', 'kind': 'measured',
                'inputs': ['following-history.jsonl', 'following-context.json']}
                for index, disposition in enumerate(plan['requirement_dispositions'])
                if case_id in disposition['case_ids']],
            'negative': {'remove': ['following-history.jsonl'],
                         'error_contains': 'Missing required source: following-history.jsonl'}}
        contract_path = folder/'measurement-contract.json'
        write(contract_path, contract)
        entry = {'case_id': case_id, 'kind': 'delivery',
                 'construction': str(construction_path.relative_to(ROOT)),
                 'construction_sha256': sha(construction_path),
                 'candidate_risk': {'status': 'physical',
                     'reason': 'A 476 m connected same-road hill route with a forward adjacent lane may be absent on the selected Native map.'},
                 'candidates': [{'id': 'fallback1',
                     'construction': str(fallback_path.relative_to(ROOT)),
                     'construction_sha256': sha(fallback_path),
                     'trigger': {'source': 'Native map route discovery log',
                         'metric': 'number of qualifying spawn-seeded hill routes',
                         'failure_condition': 'zero qualifying routes before actor spawn'},
                     'changed_knobs': ['route_seed_strategy: spawn -> topology']}],
                 'measurement_contract': str(contract_path.relative_to(ROOT)),
                 'fixture_recipe': 'work/'+ASSIGNMENT+'/diagnostic-'+suffix+'-recipe.json',
                 'measurement_procedure': {'entrypoint': 'analysis.py'},
                 'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                    'host_env_var': 'CARLA_HOST',
                                    'port_env_var': 'CARLA_PORT'}}
        prior = old_entries.get(case_id, {})
        if prior.get('construction_sha256') == entry['construction_sha256']:
            entry.update({key: prior[key] for key in
                ('offline', 'compatibility', 'physical_preparation',
                 'post_capture', 'delivery_acceptance') if key in prior})
            old_candidates = {item['id']: item for item in prior.get('candidates', [])}
            for candidate in entry['candidates']:
                old = old_candidates.get(candidate['id'], {})
                if old.get('construction_sha256') == candidate['construction_sha256']:
                    candidate.update({key: old[key] for key in ('offline', 'compatibility')
                                      if key in old})
        entries.append(entry)
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': sha(REPO/'runtime/SOURCE-MANIFEST.json'),
                'cases': entries}
    write(ROOT/'execution-manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps({'cases': len(build()['cases'])}))
