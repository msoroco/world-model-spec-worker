"""Build source-gated inline Native bundles for the nine exact 4(b) probes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHANNELS = ('public_highway_and_lane_design', 'exclusive_right_turn_control',
            'intersection_entry_and_exit', 'independent_route_intent',
            'original_lane_and_vehicle_motion', 'sightline_and_four_camera_pixels')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('returned file exceeds 2 MiB')


def build():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    ids = [c['case_id'] for c in plan['cases']]
    if len(ids) != 9 or len(set(ids)) != 9:
        raise ValueError('nine exact distinct 4(b) cases required')
    cameras = [{'name': name, 'width': 1920 if i == 0 else 1280,
                'height': 1080 if i == 0 else 720, 'fov_deg': 75,
                'pose_strategy': 'source-surveyed single-right-lane intersection and ego route'}
               for i, name in enumerate(CAMERAS)]
    recording = {'channels': [{'name': name, 'unit': 'source-bound original observation',
                               'sampling_rate_hz': 20, 'time_window': 'all 900 original frames',
                               'reference_frame': 'reviewed original intersection and lane IDs',
                               'method': 'source-sealed Native readback and four synchronized cameras',
                               'uncertainty': 'original lane design, intersection and route review pending'}
                              for name in CHANNELS],
                 'context_inputs': [{'name': 'reviewed_highway_and_turn_lane_site', 'unit': 'source record',
                                     'method': 'independent reviewed source hashes and Native map identity'}],
                 'limitations': ['Blind sightline does not change the exact turn-lane prohibition.',
                                 'Synthetic diagnostics cannot establish original travel through or legal verdict.']}
    prior_path = HERE / 'execution-manifest.json'
    prior = {x['case_id']: x for x in json.loads(prior_path.read_text()).get('cases', [])} if prior_path.exists() else {}
    entries = []
    runner = (HERE / 'native_runner.py').read_text()
    analysis = (HERE / 'analysis.py').read_text()
    measure = (HERE / 'turn_lane_observations.py').read_text()
    for case in plan['cases']:
        suffix = case['case_id'].removeprefix(AID + '__')
        config = {'assignment_id': AID, 'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
                  'actor': plan['actor'], 'selected_case_id': case['case_id'], 'case': {**case, 'recording_description': recording},
                  'duration_s': 45, 'rate_hz': 20, 'supported_case_ids': ids,
                  'required_atoms': [], 'source_packets': [], 'cameras': cameras,
                  'source_gate': 'reviewed original highway, lane design, intersection, route and Native map',
                  'control_profile': {'steer_gain': .025}}
        files = [{'path': 'runner.py', 'content': runner},
                 {'path': 'turn_lane_observations.py', 'content': measure},
                 {'path': 'analysis.py', 'content': analysis},
                 {'path': 'tests/test_bundle.py', 'content': (HERE / 'bundle_test.py').read_text()},
                 {'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'}]
        construction = {'law_id': plan['law_id'], 'cell_id': plan['cell_id'], 'actor': plan['actor'],
                        'case_id': case['case_id'], 'entrypoint': 'runner.py',
                        'recording_description': recording, 'files': files}
        path = HERE / ('construction-selected-' + suffix + '.json')
        write(path, construction)
        fallback_config = {**config, 'candidate_id': 'fallback1', 'control_profile': {'steer_gain': .035}}
        fallback_files = [dict(item) for item in files]
        next(item for item in fallback_files if item['path'] == 'config.json')['content'] = json.dumps(fallback_config, indent=2) + '\n'
        fallback = {**construction, 'files': fallback_files}
        fallback_path = HERE / ('construction-fallback1-' + suffix + '.json')
        write(fallback_path, fallback)
        entries.append({**prior.get(case['case_id'], {}), 'case_id': case['case_id'], 'kind': 'delivery',
                        'status': 'source_pending', 'construction': path.name,
                        'construction_sha256': sha(path),
                        'candidates': [{'id': 'fallback1', 'construction': fallback_path.name,
                                        'construction_sha256': sha(fallback_path),
                                        'trigger': {'source': 'original Native lane and route readback',
                                                    'metric': 'lane containment and connected departure',
                                                    'failure_condition': 'vehicle leaves surveyed lane or misses requested route'},
                                        'changed_knobs': ['controller steering gain: 0.035']}],
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Source-surveyed lane and route may differ from Native occupancy or four-camera view; original capture and review required.'},
                        'missing_proofs': ['reviewed original site', 'original Native capture',
                                           'saved-only original processing', 'physical review',
                                           'independent original delivery and comparison audit']})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
                'status': 'selected_source_pending',
                'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'cases': entries}
    write(HERE / 'execution-manifest.json', manifest)
    root = json.loads((HERE / entries[0]['construction']).read_text())
    root['measurement_plan'] = {'rate_hz': 20, 'duration_s': 45, 'required_channels': list(CHANNELS)}
    root['static_checks'] = ['exact selected identity and source hashes', 'nine source-gated Native variants']
    root['termination_rules'] = ['900 original frames at 20 Hz', 'brake, destroy owned actors and restore world on every exit']
    root['mechanisms'] = ['reviewed Native lane and connected route construction',
                          'closed-loop ego controller and four-camera original acquisition',
                          'source-bound saved measurement']
    write(HERE / 'construction.json', root)
    for item in root['files']:
        (HERE / item['path']).write_text(item['content'])
    return len(entries)


if __name__ == '__main__':
    print('source-gated selected cases:', build())
