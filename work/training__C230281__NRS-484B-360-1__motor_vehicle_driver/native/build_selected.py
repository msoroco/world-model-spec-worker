"""Build source-gated exact school-bus speed delivery constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parents[1]
AID = HERE.name
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    assignment = json.loads((REPO / 'inputs' / AID / 'assignment.json').read_text())
    if (assignment['law']['text'] != plan['source_law_text'] or
            assignment['cell']['layout'] != 'road' or
            assignment['cell']['maneuver'] != 'travel' or
            assignment['cell']['control'] != 'school_bus'):
        raise ValueError('Frozen school-bus law or cell differs')
    description = {'channels': [
        {'name': 'ego_pose', 'unit': 'm,deg', 'sampling_rate_hz': 20,
         'time_window': '30 s / 600 original frames',
         'method': 'Original Native post-tick school-bus pose joined to four cameras',
         'reference_frame': 'original Native frame',
         'uncertainty': 'Actor identity and original route require source review'},
        {'name': 'school_bus_speed', 'unit': 'mph', 'sampling_rate_hz': 20,
         'time_window': '30 s / 600 original frames',
         'method': 'Norm of original Native post-tick three-axis bus velocity',
         'reference_frame': 'original Native frame',
         'uncertainty': '50 ms sampling; no invented legal tolerance'}],
        'context_inputs': [{'name': 'school_bus_driver_and_pupil_trip_review',
            'unit': 'structured',
            'method': 'Independent original bus design, judged-driver join, pupil and trip-purpose review'}],
        'limitations': ['Requested speed is not measured speed.',
                        'A bus asset label does not prove statutory school-bus status.',
                        'Pupils aboard alone do not prove to/from-school purpose.',
                        'Synthetic diagnostic review does not establish original facts or a legal verdict.']}
    proposals, entries = [], []
    for speed in (53, 55, 57):
        cid = AID + '__' + str(speed)
        cfg = {'assignment_id': AID, 'law_id': assignment['law_id'],
               'cell_id': assignment['cell_id'], 'actor': assignment['actor'],
               'selected_case_id': cid, 'case_id': cid,
               'case': {'case_id': cid, 'recording_description': description},
               'supported_case_ids': [AID + '__' + str(x) for x in (53, 55, 57)],
               'required_atoms': [], 'source_packets': [],
               'requested_speed_mph': speed, 'rate_hz': 20, 'duration_s': 30,
               'frames': 600,
               'cameras': [{'name': name, 'width': width, 'height': height,
                            'fps': 20, 'fov_deg': 85,
                            'pose_strategy': 'source_surveyed_bus_attachment'}
                           for name, width, height in CAMERAS],
               'physical_completion': {'criterion': 'travel_progress',
                    'minimum_progress_m': 100, 'engineering_tolerances_not_legal': True,
                    'completion_goal_method': 'Source-surveyed school-bus route progress'},
               'recording_description': description,
               'physical_acceptance_claimed': False, 'legal_verdict': None}
        modules = {'runner.py': HERE / 'native/bus_capture.py',
                   'measure_speed.py': HERE / 'native/measure_speed.py',
                   'finalize.py': HERE / 'native/finalize.py'}
        files = [{'path': name, 'source': str(path.relative_to(REPO)),
                  'content': path.read_text()} for name, path in modules.items()]
        files.append({'path': 'tests/test_runner.py',
            'content': (HERE / 'native/test_bus_capture.py').read_text().replace(
                'from bus_capture import', 'from runner import')})
        files.append({'path': 'config.json',
                      'content': json.dumps(cfg, indent=2, ensure_ascii=False) + '\n'})
        construction = {'case_id': cid, 'law_id': assignment['law_id'],
            'cell_id': assignment['cell_id'], 'actor': assignment['actor'],
            'entrypoint': 'runner.py', 'files': files,
            'status': 'selected_cpu_prepared_original_unverified',
            'recording_description': description,
            'measurement_plan': {'method': '600 original post-tick velocity samples and independent bus/pupil/trip review',
                                 'duration_s': 30, 'legal_tolerance_claimed': False},
            'static_checks': ['exact frozen school-bus road/travel cell',
                              'original route survey and bus design source required',
                              'four synchronized source cameras and frame joins'],
            'termination_rules': ['600 original frames',
                                  'abort on camera or Native frame mismatch',
                                  'encoder closure and world restoration'],
            'mechanisms': ['source-surveyed school-bus blueprint and route',
                           'Native bus velocity feedback; observed speed measured separately',
                           'independent judged-driver, pupils and school-trip review']}
        path = HERE / 'selected' / str(speed) / 'construction.json'
        put(path, construction)
        contract = {'format': 'worker-measurement-contract', 'case_id': cid,
            'negative': {'remove': ['bus_motion.jsonl'],
                         'error_contains': 'Missing required source: bus_motion.jsonl'},
            'requirements': [{'disposition_index': i, 'requirement': item['requirement'],
                              'source': item['source'], 'kind': 'measured',
                              'method': 'measure_school_bus_speed',
                              'output_key': 'school_bus_speed_' + str(i),
                              'value_type': 'object',
                              'inputs': ['bus_motion.jsonl', 'video_frames.jsonl',
                                         'passenger_trip_review.json']}
                             for i, item in enumerate(plan['requirement_dispositions'])
                             if cid in item['case_ids']]}
        contract_path = HERE / ('measurement-' + str(speed) + '.json')
        put(contract_path, contract)
        proposals.append({'case_id': cid, 'target_law_id': assignment['law_id'],
            'target_type': 'judgment_sweep',
            'rationale': 'Boundary comparison of measured school-bus speed across the 55 mph statutory cap, conditional on original school transportation evidence.',
            'variable_assignments': {'requested_speed_mph': {'kind': 'controller',
                'unit': 'mph', 'value': speed}},
            'paired_probe_id': AID + '__speed_comparison',
            'deliberate_differences': ['requested_speed_mph'],
            'unresolved_judgment_calls': ['school-bus design', 'judged driver is bus driver',
                                         'pupils aboard', 'to/from-school trip purpose'],
            'recording_description': description})
        entries.append({'case_id': cid, 'kind': 'delivery',
            'construction': str(path.relative_to(HERE)),
            'construction_sha256': sha(path),
            'measurement_contract': contract_path.name,
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'fixture_recipe': 'work/' + AID + '/diagnostic-' + str(speed) + '-primary-recipe.json',
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
            'candidate_risk': {'status': 'none',
                'reason': 'Actual bus asset and route need original review; no measured primary failure defines an honest fallback trigger'},
            'candidates': []})
    put(HERE / 'proposals/cases.json', {'format': 'worker-case-proposals',
        'cell_id': assignment['cell_id'], 'actor': assignment['actor'],
        'law_id': assignment['law_id'], 'status': 'draft', 'cases': proposals,
        'sweep_specs': [], 'sweeps_expanded': True})
    batch = json.loads((REPO / 'batch.json').read_text())
    put(HERE / 'draft-native-manifest.json', {'format': 'worker-execution-manifest',
        'assignment_id': AID, 'status': 'draft_incomplete_proofs',
        'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
        'cases': entries})
    put(HERE / 'config.json', json.loads(next(x['content'] for x in
        json.loads((HERE / entries[0]['construction']).read_text())['files']
        if x['path'] == 'config.json')))
    put(HERE / 'construction.json', json.loads((HERE / entries[0]['construction']).read_text()))
    for name, source in (("runner.py", "bus_capture.py"),
                         ("measure_speed.py", "measure_speed.py"),
                         ("finalize.py", "finalize.py")):
        (HERE / name).write_text((HERE / "native" / source).read_text())
    tests = HERE / 'tests'
    tests.mkdir(exist_ok=True)
    (tests / 'test_runner.py').write_text(
        (HERE / 'native/test_bus_capture.py').read_text().replace(
            'from bus_capture import', 'from runner import'))
    return {'cases': 3, 'manifest_sha256': sha(HERE / 'draft-native-manifest.json')}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
