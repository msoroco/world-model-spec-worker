"""Bind the six selected constructions and source contracts to offline receipts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parents[1]
NATIVE = FOLDER / 'native'
IDENT = FOLDER.name


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, item):
    path.write_text(json.dumps(item, indent=2, allow_nan=False) + '\n')


def offline(index, case_id, candidate, construction_hash):
    log = f'native/condition-{index}-{candidate}-offline-tests.log'
    return {'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{IDENT}/native/draft-manifest.json --case {case_id} --candidate {candidate} --output .runtime-work/c229351-offline-v7-{index}-{candidate}',
            'exit_code': 0, 'construction_sha256': construction_hash,
            'log': log, 'log_sha256': digest(FOLDER / log)}


def main():
    draft = json.loads((NATIVE / 'draft-manifest.json').read_text())
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    entries = []
    for index, old in enumerate(draft['cases']):
        case_id = old['case_id']
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
                    'requirements': [], 'negative': {'remove': ['road_geometry.json'],
                    'error_contains': 'Missing required source: road_geometry.json'}}
        measurements = [
            ('roadway_rest_geometry', 'measure_roadway_rest_geometry', 'measured',
             ['native_samples.jsonl', 'video_frames.jsonl', 'road_geometry.json', 'road_edge_survey.json']),
            ('activity_source_context', 'measure_activity_source_context', 'sourced_context',
             ['native_samples.jsonl', 'activity_context.json', 'body_history.jsonl']),
            ('chapter_exception_context', 'measure_chapter_exception_context', 'sourced_context',
             ['road_edge_survey.json', 'activity_context.json'])]
        for disposition_index, ((key, method, kind, inputs), row) in enumerate(zip(measurements, plan['requirement_dispositions'])):
            contract['requirements'].append({'disposition_index': disposition_index,
                'requirement': row['requirement'], 'source': row['source'],
                'output_key': key, 'method': method, 'value_type': 'object',
                'kind': kind, 'inputs': inputs})
        contract_name = f'native/selected-{index}-measurement-contract.json'
        write(FOLDER / contract_name, contract)
        primary = 'native/' + old['construction']
        fallback = old['candidates'][0]
        fallback_name = 'native/' + fallback['construction']
        entry = {'case_id': case_id, 'kind': 'delivery',
            'construction': primary, 'construction_sha256': old['construction_sha256'],
            'candidate_risk': {'status': 'physical', 'reason':
                'Original at-rest vehicle motion and camera/body containment require Native review'},
            'candidates': [{'id': 'fallback1', 'construction': fallback_name,
                'construction_sha256': fallback['construction_sha256'],
                'trigger': {'source': 'original Native body_history.jsonl and video_frames.jsonl',
                            'metric': '600-frame stationary body containment and four-camera visibility',
                            'failure_condition': 'Primary does not remain at rest within roadway and cameras for the selected interval'},
                'changed_knobs': ['controller_mode: service brake plus hand brake instead of service brake'],
                'offline': offline(index, case_id, 'fallback1', fallback['construction_sha256'])}],
            'delivery_readiness': 'incomplete',
            'measurement_contract': contract_name,
            'measurement_procedure': {'entrypoint': 'finalize.py',
                'output_schema': 'c229351-roadway-rest-analysis-v1'},
            'fixture_recipe': f'work/{IDENT}/native/fixture-recipe-{index}.json',
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
            'acquisition': {'roadway_rest_geometry': {'entrypoint': 'capture.py',
                'method': 'same-tick original Native readback',
                'evidence': 'native_samples.jsonl, video_frames.jsonl, road_geometry.json and road_edge_survey.json'},
                'activity_source_context': {'entrypoint': 'capture.py',
                'method': 'same-tick original Native readback',
                'evidence': 'native_samples.jsonl, activity_context.json and body_history.jsonl'},
                'chapter_exception_context': {'entrypoint': 'capture.py',
                'method': 'survey and authority context retained separately',
                'evidence': 'road_edge_survey.json and activity_context.json'}},
            'offline': offline(index, case_id, 'primary', old['construction_sha256'])}
        construction = json.loads((FOLDER / primary).read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        for channel in config['recording_description']['channels']:
            name = channel['name']
            derived = name in ('edge_parallel_angle_deg', 'lawful_traffic_heading_angle_deg')
            entry['acquisition'][name] = {
                'entrypoint': 'finalize.py' if derived else 'capture.py',
                'method': 'saved original Native pose and roadway geometry projection' if derived
                          else 'same-tick Native readback with saved source context',
                'evidence': 'native_samples.jsonl, video_frames.jsonl, body_history.jsonl, '
                            'road_geometry.json, road_edge_survey.json, activity_context.json'}
        entries.append(entry)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': IDENT,
        'runtime_manifest_sha256': digest(ROOT / 'runtime/SOURCE-MANIFEST.json'),
        'status': 'partial', 'cases': entries}
    write(FOLDER / 'execution-manifest.json', manifest)


if __name__ == '__main__':
    main()
