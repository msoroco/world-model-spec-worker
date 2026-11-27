"""Build exact selected primary and visibility fallback private-way entry constructions."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
TERMS = ('st.driveway_or_alley_entrance', 'st.highway', 'drv.entering_intersection',
         'drv.approaching', 'drv.yields_to', 'drv.arrival_order',
         'drv.hard_deceleration', 'rel.occupies', 'kin.position', 'kin.heading', 'kin.speed')
SOURCES = ('road.xodr', 'private-entry-context.json', 'private-entry-actors.jsonl',
           'private-entry-review.json', 'video_frames.jsonl', 'trace.jsonl',
           'capture/manifest.json', *(view + '.mkv' for view in VIEWS))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False).rstrip() + '\n')


def main():
    camera_specs = [('overview', 1920, 1080), ('approach', 1280, 720),
                    ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]
    cameras = [{'name': name, 'width': width, 'height': height,
                'pose_strategy': 'static private-way entry and both highway approaches',
                'fov_deg': 85} for name, width, height in camera_specs]
    description = {'channels': [{'name': term, 'unit': 'structured', 'sampling_rate_hz': 20,
        'method': 'original Native all-vehicle body and frame source, measured after capture',
        'time_window': 'all 600 frames across 30 seconds',
        'reference_frame': 'authored OpenDRIVE with Native road/lane readback',
        'uncertainty': '50 ms frame sampling; legal right-of-way unresolved'} for term in TERMS],
        'context_inputs': [{'name': 'private_way_and_highway', 'unit': 'source context',
                            'method': 'original Native road/lane waypoint survey'}],
        'limitations': ['CPU diagnostic does not establish realized Native crossing or pixels',
                        'Conflict arrival order and speed drops do not decide legal yielding',
                        'Every approaching highway vehicle must be inventoried in original source']}
    ids = [ROOT.name + '__probe_a', ROOT.name + '__probe_b']
    cases = []
    source_files = ('runner.py', 'geometry.py', 'finalize.py', 'tests/test_native.py')
    for index, case_id in enumerate(ids):
        suffix = f'probe_{"a" if index == 0 else "b"}'
        for candidate in ('primary', 'fallback1'):
            config = {'case_id': case_id, 'selected_case_id': case_id,
                'supported_case_ids': ids, 'case_suffix': suffix, 'candidate_id': candidate,
                'cell_id': 'C177626', 'law_id': 'NRS-484B-260',
                'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'duration_s': 30,
                'required_atoms': [], 'source_packets': [], 'case': {'case_id': case_id},
                'cameras': cameras,
                'physical_target': {'behavior': 'yield until all approaching highway vehicles pass' if index == 0
                                    else 'enter between two approaching highway arrivals'},
                'recording_description': description,
                'status': 'selected_cpu_construction_physical_and_legal_unverified'}
            files = [{'path': name, 'content': (ROOT / 'native' / name).read_text()}
                     for name in source_files]
            files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
            construction = {'case_id': case_id, 'law_id': 'NRS-484B-260',
                'cell_id': 'C177626', 'actor': 'motor_vehicle_driver',
                'entrypoint': 'runner.py', 'files': files,
                'recording_description': description,
                'measurement_plan': {'entrypoint': 'finalize.py',
                                     'required_sources': list(SOURCES),
                                     'status': 'source_bound_cpu_prepared'},
                'static_checks': ['private-way approach road ends at highway edge',
                                  'two inventoried highway approach vehicles and four cameras',
                                  '600 frames at 20 Hz with all vehicle bodies'],
                'termination_rules': ['600 original frames', 'restore exclusive Native world'],
                'mechanisms': ['ego enters from private way toward paved highway',
                               'both highway vehicles retain identical planned trajectories',
                               'entry release frame is the sole controlled comparison variable',
                               'fallback shifts two static camera poses for source visibility'],
                'status': 'selected_cpu_prepared_physical_and_legal_unverified'}
            path = ROOT / 'cases' / suffix / candidate / 'construction.json'
            put(path, construction)
            if candidate == 'primary':
                primary_path, primary_hash = path, sha(path)
            else:
                fallback_path, fallback_hash = path, sha(path)
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
            'requirements': [{'disposition_index': 0, 'requirement': 'NRS-484B-260',
                'source': 'NRS 484B.260', 'kind': 'measured', 'method': 'measure_entry',
                'output_key': 'private_way_entry', 'value_type': 'object',
                'inputs': list(SOURCES)}],
            'negative': {'remove': ['private-entry-actors.jsonl'],
                         'error_contains': 'Missing required source: private-entry-actors.jsonl'}}
        contract_path = ROOT / 'cases' / suffix / 'measurement-contract.json'
        put(contract_path, contract)
        cases.append({'case_id': case_id, 'kind': 'delivery',
            'construction': str(primary_path.relative_to(ROOT)),
            'construction_sha256': primary_hash,
            'candidate_risk': {'status': 'physical',
                'reason': 'Original highway-approach and private-way entry may not remain visible from the static approach/corner cameras; candidate changes only their pose.'},
            'candidates': [{'id': 'fallback1',
                'construction': str(fallback_path.relative_to(ROOT)),
                'construction_sha256': fallback_hash,
                'trigger': {'source': 'original camera decode and visibility review',
                            'metric': 'approach and reference_corner video coverage',
                            'failure_condition': 'entry or either approaching vehicle not continuously visible'},
                'changed_knobs': ['approach/reference_corner camera x minus 6 m and z plus 3 m']}],
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'delivery_readiness': 'incomplete',
            'measurement_contract': str(contract_path.relative_to(ROOT)),
            'fixture_recipe': f'work/{ROOT.name}/cases/{suffix}/recipe.json',
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
            'acquisition': {name: {'entrypoint': 'runner.py',
                'method': 'Original Native all-vehicle bodies, road/lane survey and synchronized four cameras',
                'evidence': list(SOURCES)} for name in TERMS},
            'offline': {}, 'compatibility': {}, 'negative': {}, 'post_capture': {},
            'physical_preparation': {}, 'delivery_acceptance': {}})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ROOT.name,
                'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'status': 'partial', 'cases': cases}
    put(ROOT / 'execution-manifest.json', manifest)
    construction = json.loads((ROOT / cases[0]['construction']).read_text())
    put(ROOT / 'construction.json', construction)
    for file in construction['files']:
        path = ROOT / file['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(file['content'])
    print(json.dumps({'cases': ids, 'primary_sha256': [c['construction_sha256'] for c in cases]}))


if __name__ == '__main__':
    main()
