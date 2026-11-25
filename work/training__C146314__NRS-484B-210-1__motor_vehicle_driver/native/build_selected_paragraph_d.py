"""Build exact paragraph (d) selected CPU drafts for saved-source integration."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
OUT = HERE / 'selected-paragraph-d'
CAMERAS = [('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]
SOURCES = ['native-raw-actors.jsonl', 'video_frames.jsonl',
           'native-map-readback.json', 'native-capture-report.json',
           'source-review.json', 'one-way-pass.xodr'] + [
               name + '.mkv' for name, _, _ in CAMERAS]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def recording(case_id):
    channels = [('ego_pose', 'structured'),
                ('right_pass_geometry', 'structured'),
                ('four_source_views', 'video'),
                ('pavement_context', 'structured')]
    return {'channels': [{'name': name, 'unit': unit,
        'sampling_rate_hz': 20,
        'method': 'retained original Native actor/map pose and four camera frame join',
        'time_window': '600 original Native frames',
        'reference_frame': 'authored OpenDRIVE road 210',
        'uncertainty': '50 ms samples; designation, pavement significance and pixels await source review'}
        for name, unit in channels],
        'context_inputs': [{'name': 'one_way_designation_source',
            'unit': 'structured',
            'method': 'independent source review joined to original Native map readback'}],
        'limitations': ['Authored geometry and requested cone do not settle statutory permission or physical completion.',
            'Original Native motion, one-way designation and four camera pixels require later review.']}


def build():
    plan = json.loads((CASE / 'case-plan.json').read_text())
    if plan['assignment_id'] != CASE.name or len(plan['cases']) != 15:
        raise ValueError('Frozen-source case plan identity differs')
    selected = {item['case_id'] for item in plan['cases'][:2]}
    if selected != {CASE.name + '__witness_1', CASE.name + '__witness_2'}:
        raise ValueError('Paragraph (d) pair differs')
    runtime = json.loads((ROOT / 'batch.json').read_text())['runtime']['root']
    entries = []
    for suffix, source_name in [('witness_1', 'current-primary'),
                                ('witness_2', 'current-contrast')]:
        source = HERE / source_name
        case_id = CASE.name + '__' + suffix
        cfg = json.loads((source / 'config.json').read_text())
        cfg.update(selected_case_id=case_id, supported_case_ids=sorted(selected),
                   required_atoms=[], source_packets=[], case={'case_id': case_id},
                   cameras=[{'name': name, 'width': width, 'height': height,
                       'pose_strategy': 'fixed overview or ego-mounted source camera',
                       'fov_deg': 85 if name == 'overview' else 90}
                       for name, width, height in CAMERAS],
                   status='selected_cpu_draft_physical_unverified')
        config_text = json.dumps(cfg, indent=2, allow_nan=False) + '\n'
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
            'requirements': [{'disposition_index': 0,
                'requirement': plan['requirement_dispositions'][0]['requirement'],
                'source': plan['requirement_dispositions'][0]['source'],
                'output_key': 'paragraph_d_source_observation',
                'method': 'measure_paragraph_d', 'value_type': 'object',
                'kind': 'measured', 'inputs': SOURCES}],
            'negative': {'remove': ['source-review.json'],
                'error_contains': 'Missing required source: source-review.json'}}
        files = [{'path': name, 'content': (source / name).read_text()}
                 for name in ('one-way-pass.xodr', 'assignment-source.json',
                              'case-plan.json', 'requested-tracks.jsonl',
                              'check.py', 'capture.py', 'saved.py',
                              'tests/test_exact.py')]
        files.extend([{'path': 'config.json', 'content': config_text},
            {'path': 'finalize.py',
             'content': (HERE / 'current_pair_finalize.py').read_text()},
            {'path': 'measurement-contract.json',
             'content': json.dumps(contract, indent=2, allow_nan=False) + '\n'}])
        construction = {'case_id': case_id, 'cell_id': 'C146314',
            'law_id': 'NRS-484B-210-1', 'actor': 'motor_vehicle_driver',
            'entrypoint': 'capture.py', 'files': files,
            'recording_description': recording(case_id),
            'measurement_plan': {'source': 'original joined actor/map/camera records',
                'finalizer': 'finalize.py', 'legal_verdict': None},
            'static_checks': ['600 source-bound request frames',
                'four named camera views', 'saved-only actor/body/frame join'],
            'termination_rules': {'requested_frames': 600,
                'stop_on_error': True},
            'mechanisms': {'road': 'one-way-pass.xodr',
                'controller': 'capture.py', 'saved_meter': 'saved.py'},
            'status': 'selected_cpu_draft_physical_unverified',
            'original_native_observed': False, 'delivery_ready': False}
        directory = OUT / suffix / 'primary'
        path = directory / 'construction.json'
        put(path, construction)
        put(OUT / suffix / 'measurement-contract.json', contract)
        entries.append({'case_id': case_id, 'kind': 'delivery',
            'construction': suffix + '/primary/construction.json',
            'construction_sha256': sha(path),
            'measurement_contract': suffix + '/measurement-contract.json',
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'candidate_risk': {'status': 'physical',
                'reason': 'Original pass, pavement significance, source review and four camera pixels are unverified.'},
            'candidates': [],
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}})
    manifest = {'format': 'worker-execution-manifest',
        'assignment_id': CASE.name,
        'runtime_manifest_sha256': sha(ROOT / runtime / 'SOURCE-MANIFEST.json'),
        'status': 'selected_pair_cpu_draft_only',
        'delivery_ready': False, 'original_native_observed': False,
        'cases': entries}
    put(OUT / 'manifest.json', manifest)
    return {'cases': len(entries), 'manifest_sha256': sha(OUT / 'manifest.json'),
            'construction_sha256': [item['construction_sha256'] for item in entries]}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
