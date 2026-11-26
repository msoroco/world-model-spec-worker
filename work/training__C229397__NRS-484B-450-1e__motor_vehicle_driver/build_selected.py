"""Bind the exact 14-case Native draft to recorded-only selected constructions."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    draft = json.loads((FOLDER / 'draft-execution-manifest.json').read_text())
    description = {'channels': [{'name': 'crosswalk_observation', 'unit': 'mixed',
        'sampling_rate_hz': 20, 'method': 'original footprint and crosswalk polygon readback',
        'time_window': '600 frames', 'reference_frame': 'Native world XY',
        'uncertainty': '50 ms source interval; activity and legal exceptions require review'}],
        'context_inputs': [{'name': 'exception_authority', 'unit': 'structured',
            'method': 'reviewed hash-bound source packet; legal applicability unverified'}],
        'limitations': ['Original Native geometry and pixels require local execution',
                        'No legal verdict is derived from overlap or rest duration']}
    proposals = {'cell_id': plan['cell_id'], 'actor': plan['actor'], 'status': 'draft',
                 'cases': []}
    cases = []
    for entry in draft['cases']:
        case_id = entry['case_id']
        suffix = case_id.rsplit('__', 1)[-1]
        source = json.loads((FOLDER / entry['construction']).read_text())
        files = {item['path']: item['content'] for item in source['files']}
        config = json.loads(files['config.json'])
        config.update(selected_case_id=case_id, case={'case_id': case_id},
                      required_atoms=[], source_packets=[],
                      recording_description=description)
        files['config.json'] = json.dumps(config, indent=2) + '\n'
        files['finalize.py'] = (FOLDER / 'finalize.py').read_text()
        files['measure_crosswalk.py'] = (FOLDER / 'measure_crosswalk.py').read_text()
        source.update(files=[{'path': path, 'content': content}
                             for path, content in files.items()],
                      recording_description=description,
                      status='selected_native_cpu_draft_not_delivery_prepared')
        path = FOLDER / 'native' / 'bundles' / suffix / 'construction.json'
        write(path, source)
        disposition_index = next(i for i, row in enumerate(plan['requirement_dispositions'])
                                 if case_id in row['case_ids'])
        disposition = plan['requirement_dispositions'][disposition_index]
        inputs = ['crosswalk-source.json', 'actor-sources.jsonl',
                  'camera-frames.jsonl', 'exception-context.json',
                  'road.xodr', 'video_frames.jsonl']
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
            'requirements': [{'disposition_index': disposition_index,
                'requirement': disposition['requirement'], 'source': disposition['source'],
                'output_key': 'crosswalk_observation', 'method': 'crosswalk_observation',
                'value_type': 'object', 'kind': 'measured', 'inputs': inputs}],
            'negative': {'remove': ['crosswalk-source.json'],
                         'error_contains': 'Missing required source: crosswalk-source.json'}}
        write(FOLDER / ('measurement-' + suffix + '.json'), contract)
        cases.append({'case_id': case_id, 'kind': 'delivery',
            'construction': str(path.relative_to(FOLDER)),
            'construction_sha256': sha(path),
            'candidate_risk': {'status': 'physical',
                'reason': 'Original Native crosswalk geometry and activity remain unverified'},
            'candidates': [], 'delivery_readiness': 'incomplete',
            'measurement_contract': 'measurement-' + suffix + '.json',
            'measurement_procedure': {'entrypoint': 'finalize.py',
                                      'output_schema': 'c229397-crosswalk-analysis-v1'},
            'fixture_recipe': 'work/' + FOLDER.name + '/selected-recipe-' + suffix + '.json',
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
            'acquisition': {name: {'entrypoint': 'capture.py',
                'method': 'same-tick original Native readback',
                'evidence': 'actor-sources.jsonl, camera-frames.jsonl and crosswalk-source.json'}
                for name in ('crosswalk_observation', 'exception_authority')}})
        proposals['cases'].append({'case_id': case_id,
            'target_law_id': plan['law_id'], 'target_type': 'controlled_attempt',
            'rationale': next(case['physical_target'] for case in plan['cases']
                              if case['case_id'] == case_id),
            'recording_description': description,
            'variable_assignments': {'crosswalk_target': {'kind': 'subject_behavior',
                'value': config['target_variant']}},
            'unresolved_judgment_calls': ['actual stop, stand or park activity',
                                          'exception applicability and legal verdict']})
    write(FOLDER / 'proposals/cases.json', proposals)
    write(FOLDER / 'execution-manifest.json', {'format': 'worker-execution-manifest',
        'assignment_id': FOLDER.name,
        'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
        'status': 'partial', 'cases': cases})


if __name__ == '__main__':
    build()
