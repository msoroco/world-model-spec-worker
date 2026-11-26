"""Bind exact C295180 stop-line selected CPU candidates and diagnostic sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]
SEED = ROOT / 'work/training__C111325__NRS-484A-450-2__motor_vehicle_driver'
OLD = SEED.name
NEW = PACKAGE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def adapt(value):
    text = json.dumps(value, ensure_ascii=False)
    text = text.replace(OLD + '__line_stop', NEW + '__selected_ef239a06__condition_a')
    text = text.replace(OLD + '__line_pass', NEW + '__selected_ef239a06__condition_b')
    text = text.replace(OLD + '__marked_line_comparison', NEW + '__selected_ef239a06__comparison')
    text = text.replace('C111325', 'C295180')
    return json.loads(text)


def build():
    source = json.loads((SEED / 'proposals/cases.json').read_text())
    proposals = {'cell_id': 'C295180', 'actor': 'motor_vehicle_driver',
                 'status': 'draft', 'sweep_specs': [],
                 'cases': [adapt(case) for case in source['cases']
                           if case['case_id'] in (OLD + '__line_stop', OLD + '__line_pass')]}
    write(PACKAGE / 'proposals/cases.json', proposals)
    runtime_hash = sha(ROOT / 'runtime/SOURCE-MANIFEST.json')
    entries = []
    for condition, label in (('a', 'line_stop'), ('b', 'line_pass')):
        case = NEW + '__selected_ef239a06__condition_' + condition
        seed = json.loads((SEED / ('selected-' + label + '-primary-construction.json')).read_text())
        seed_config = json.loads(next(f['content'] for f in seed['files'] if f['path'] == 'config.json'))
        config = adapt(seed_config)
        config['case_id'] = case
        config['selected_case_id'] = case
        config['supported_case_ids'] = [item['case_id'] for item in proposals['cases']]
        config['case'] = next(item for item in proposals['cases'] if item['case_id'] == case)
        config['duration_frames'] = 600
        config['cameras'] = [dict(camera, fps=20) for camera in config['cameras']]
        config['stop_policy'] = 'full_stop' if condition == 'a' else 'rolling'
        config['stop_sign_governs'] = True
        config['near_crosswalk_present'] = False
        config['marked_stop_line_x_m'] = 0
        config['physical_verified'] = False
        config['legal_verdict'] = None
        config['spawn_y_m'] = -61
        recording = config['recording_description']
        def construction(spawn):
            specific = dict(config, spawn_y_m=spawn)
            files = [{'path': 'config.json', 'content': json.dumps(specific, indent=2, ensure_ascii=False) + '\n'},
                     {'path': 'runner.py', 'content': (HERE / 'draft_runner.py').read_text()},
                     {'path': 'tests/test_offline.py', 'content': (HERE / 'test_draft_offline.py').read_text()}]
            files += [{'path': name, 'content': (HERE / name).read_text()} for name in
                      ('authored-road.xodr', 'road_source.py', 'stop_line_request.py',
                       'saved_stop_line.py', 'live_capture.py', 'finalize.py')]
            return {'format': 'worker-inline-construction', 'case_id': case,
                    'cell_id': 'C295180', 'actor': 'motor_vehicle_driver',
                    'entrypoint': 'runner.py', 'files': files,
                    'recording_description': recording, 'status': 'selected_cpu_draft'}
        primary = PACKAGE / ('selected-condition-' + condition + '-primary-construction.json')
        fallback = PACKAGE / ('selected-condition-' + condition + '-fallback1-construction.json')
        write(primary, construction(-61))
        write(fallback, construction(-66))
        contract = {'format': 'worker-measurement-contract', 'case_id': case,
                    'requirements': [{'disposition_index': 0, 'requirement': 'text-0',
                                      'source': 'NRS 484A.450(2)', 'output_key': 'marked_line_stop',
                                      'method': 'measure_marked_line_stop', 'value_type': 'object',
                                      'kind': 'measured',
                                      'inputs': ['native_samples.jsonl', 'road.xodr']}],
                    'negative': {'remove': ['road.xodr'],
                                 'error_contains': 'Missing required source: road.xodr'}}
        contract_path = PACKAGE / ('selected-condition-' + condition + '-measurement-contract.json')
        write(contract_path, contract)
        entries.append({'case_id': case, 'kind': 'delivery',
                        'construction': primary.name, 'construction_sha256': sha(primary),
                        'fixture_recipe': 'work/' + NEW + '/selected-condition-' + condition + '-fixture-recipe.json',
                        'measurement_contract': contract_path.name,
                        'measurement_procedure': {'entrypoint': 'finalize.py'},
                        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                           'host_env_var': 'CARLA_HOST',
                                           'port_env_var': 'CARLA_PORT'},
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Subject can cross the line before intended stop window'},
                        'candidates': [{'id': 'fallback1', 'construction': fallback.name,
                                        'construction_sha256': sha(fallback),
                                        'changed_knobs': ['move subject spawn 5 m farther from marked line'],
                                        'trigger': {'source': 'native_samples.jsonl',
                                                    'metric': 'first_front_stop_line_crossing_frame',
                                                    'failure_condition': 'front body crosses line before requested stop window'}}]})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': NEW,
                'runtime_manifest_sha256': runtime_hash,
                'status': 'selected_cpu_draft', 'delivery_ready': False,
                'original_native_observed': False, 'cases': entries}
    write(PACKAGE / 'selected-draft-execution-manifest.json', manifest)
    return {'cases': len(entries), 'runtime_manifest_sha256': runtime_hash}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
