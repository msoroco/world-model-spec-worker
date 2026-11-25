"""Promote source-reviewed passing requests to exact selected bundle drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DISTANCES = (70, 120, 170)
CANDIDATES = ('primary', 'fallback1')
ATOM_CHANNELS = {'st.sight_distance': 'm', 'rel.visible': 'boolean',
                 'kin.speed': 'm/s', 'native_actor_poses': 'structured',
                 'passing_response': 'structured'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def recording(plan):
    units = {row['name']: row['unit'] for row in plan['observations']}
    units.update(ATOM_CHANNELS)
    channels = [{'name': name, 'unit': unit,
                 'method': 'Retain original Native actor, road, sightline and synchronized camera source; source-bound saved analysis',
                 'time_window': 'entire 30 s / 600-frame attempt',
                 'reference_frame': 'original Native frame and time',
                 'uncertainty': '50 ms sample; actual sightline, highway status and interference require original review',
                 'sampling_rate_hz': 20}
                for name, unit in sorted(units.items())]
    return {'channels': channels, 'context_inputs': [],
            'limitations': ['Source proxies do not establish statutory sufficient distance or safe operation',
                            'Synthetic CPU tests do not prove Native CARLA motion or pixels']}


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    description = recording(plan)
    selected_runner = (HERE / 'native/runner.py').read_text().replace(
        "'status': 'unselected_native_request'", "'status': 'selected_delivery_request'")
    selected_runner = selected_runner.replace(
        "road = HERE/'road.xodr' if canonical else bundle/'road.xodr'",
        "road = bundle/'road.xodr' if (bundle/'road.xodr').is_file() else CASE/'native/road.xodr'")
    selected_runner = selected_runner.replace(
        "road = HERE/'road.xodr' if bundle.resolve() == (HERE/'drafts'/str(distance)/candidate).resolve() else bundle/'road.xodr'",
        "road = bundle/'road.xodr' if (bundle/'road.xodr').is_file() else CASE/'native/road.xodr'")
    selected_runner = selected_runner.replace(
        "if output.exists():\n        raise ValueError('Native output must be a fresh directory')\n    output.mkdir(parents=True)",
        "if output.exists() and output != Path(bundle).resolve():\n        raise ValueError('Native output must be its selected materialized bundle')\n    output.mkdir(parents=True, exist_ok=True)")
    selected_runner = selected_runner.replace(
        "    client = carla.Client(host, int(port))",
        "    if not (output/'road.xodr').is_file():\n        (output/'road.xodr').write_bytes(road.read_bytes())\n    client = carla.Client(host, int(port))")
    if "'status': 'selected_delivery_request'" not in selected_runner:
        raise ValueError('Selected runner status adaptation absent')
    finalizer = (HERE / 'selected_finalize.py').read_text()
    pass_measure = (HERE / 'native/measure_pass.py').read_text()
    response_measure = (HERE / 'native/measure_response.py').read_text()
    constructions = []
    cases = []
    proposals = []
    for distance in DISTANCES:
        plans = []
        for candidate in CANDIDATES:
            draft = json.loads((HERE / f'runtime-draft/{distance}-{candidate}-construction.json').read_text())
            files = draft['files']
            files[:] = [item for item in files if item['path'] != 'road.xodr']
            config_item = next(item for item in files if item['path'] == 'config.json')
            config = json.loads(config_item['content'])
            config.update(status='selected_delivery_request', selected_case_id=config['case_id'],
                          required_atoms=['st.sight_distance', 'rel.visible'], source_packets=[],
                          mandatory_channels=[channel['name'] for channel in description['channels']],
                          recording_description=description,
                          cameras=[{'name': name, 'width': width, 'height': height,
                                    'pose_strategy': 'original Native synchronized subject and road view',
                                    'fov_deg': 90} for name, width, height in
                                   (('overview', 1920, 1080), ('approach', 1280, 720),
                                    ('reference_corner', 1280, 720),
                                    ('driver_reference', 1280, 720))],
                          case={'case_id': config['case_id']})
            config_item['content'] = json.dumps(config, indent=2, sort_keys=True) + '\n'
            next(item for item in files if item['path'] == 'runner.py')['content'] = selected_runner
            for name, content in [('finalize.py', finalizer),
                                  ('measure_pass.py', pass_measure),
                                  ('measure_response.py', response_measure)]:
                matches = [item for item in files if item['path'] == name]
                if matches:
                    matches[0]['content'] = content
                else:
                    files.append({'path': name, 'content': content})
            draft.update(status='selected_delivery_draft', recording_description=description,
                         measurement_plan={'method': 'source-bound saved pass and separate vehicle-response observations',
                                           'status': 'selected_draft'},
                         static_checks=['600 original frame joins', 'four synchronized cameras',
                                        'source-hashed Native and OpenDRIVE inputs'],
                         termination_rules=['retain 600 original frames or explicit failed capture',
                                            'close encoders and restore world settings'])
            path = HERE / f'selected-{distance}-{candidate}-construction.json'
            write(path, draft)
            constructions.append({'distance_m': distance, 'candidate_id': candidate,
                                  'case_id': config['case_id'],
                                  'construction_sha256': sha(path),
                                  'file_count': len(files)})
            plans.append({'id': candidate, 'construction': path.name,
                          'construction_sha256': sha(path)})
        cases.append({'case_id': plan['assignment_id'] + '__' + str(distance),
                      'kind': 'delivery',
                      'construction': plans[0]['construction'],
                      'construction_sha256': plans[0]['construction_sha256'],
                      'measurement_procedure': {'entrypoint': 'finalize.py'},
                      'measurement_contract': f'selected-{distance}-measurement-contract.json',
                      'fixture_recipe': f'work/{plan["assignment_id"]}/selected-{distance}-recipe.json',
                      'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                         'host_env_var': 'CARLA_HOST',
                                         'port_env_var': 'CARLA_PORT'},
                      'candidates': [dict(plans[1],
                                          trigger={'source': 'native-observed.jsonl',
                                                   'metric': 'entry_oncoming_body_gap_m',
                                                   'failure_condition': 'source-measured original gap below authored 100 m routing trigger'},
                                          changed_knobs=['delay left-of-center entry on original Native frame clock'])],
                      'candidate_risk': {'status': 'physical',
                                         'reason': 'Original hill-crest sightline, gap and pass motion may not realize request'}})
        proposals.append({'case_id': plan['assignment_id'] + '__' + str(distance),
                          'target_law_id': plan['law_id'], 'target_type': 'judgment_sweep',
                          'rationale': 'Requested source-measurement comparison only; no numeric statutory sufficiency or interference boundary is inferred',
                          'variable_assignments': {
                              'requested_oncoming_distance_m': {'kind': 'controller', 'unit': 'm',
                                                                 'value': distance},
                              'actual_entry_oncoming_body_gap_m': {'kind': 'subject_behavior',
                                                                    'unit': 'm', 'value': None}},
                          'unresolved_judgment_calls': ['sufficient distance', 'safe operation'],
                          'recording_description': description,
                          'paired_probe_id': 'C102951-passing-distance',
                          'deliberate_differences': ['requested_oncoming_distance_m'],
                          'probe': {'primary_variable': 'actual_entry_oncoming_body_gap_m',
                                    'comparison_or_standard': 'qualitative sufficient distance and no interference; no numeric cutoff',
                                    'target_value_or_branch': distance}})
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': plan['assignment_id'],
                'runtime_manifest_sha256': sha(HERE.parents[1] / 'runtime/SOURCE-MANIFEST.json'),
                'status': 'selected_draft_missing_official_proofs', 'cases': cases}
    write(HERE / 'selected-draft-execution-manifest.json', manifest)
    proposal = {'cell_id': plan['cell_id'], 'actor': plan['actor'], 'status': 'draft',
                'sweep_specs': [], 'sweeps_expanded': True, 'cases': proposals}
    proposal_folder = HERE / 'proposals'
    proposal_folder.mkdir(exist_ok=True)
    write(proposal_folder / 'cases.json', proposal)
    print(json.dumps({'constructions': constructions}, sort_keys=True))


if __name__ == '__main__':
    main()
