"""Build paragraph (d) component pair from the source-bound witness drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
SOURCE = HERE / 'selected-paragraph-d'
OUT = HERE / 'exception-4'
RENAMES = {'__witness_1': '__exception_4_2',
           '__witness_2': '__exception_4_1'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def rename(text):
    for old, new in RENAMES.items():
        text = text.replace(old, new)
    return text


def build():
    entries = []
    for index, source_suffix in ((1, 'witness_2'), (2, 'witness_1')):
        suffix = f'exception_4_{index}'
        case_id = CASE.name + '__' + suffix
        source = SOURCE / source_suffix / 'primary' / 'construction.json'
        construction = json.loads(source.read_text())
        construction['case_id'] = case_id
        construction['status'] = 'paragraph_d_component_cpu_draft_physical_unverified'
        construction['measurement_plan']['legal_verdict'] = None
        for item in construction['files']:
            if item['path'] in ('assignment-source.json', 'case-plan.json', 'one-way-pass.xodr'):
                continue
            item['content'] = rename(item['content'])
        files = {item['path']: item for item in construction['files']}
        config = json.loads(files['config.json']['content'])
        config['case_id'] = case_id
        config['selected_case_id'] = case_id
        config['case'] = {'case_id': case_id}
        config['supported_case_ids'] = [CASE.name + '__exception_4_1',
                                        CASE.name + '__exception_4_2']
        config['tracks_sha256'] = hashlib.sha256(
            files['requested-tracks.jsonl']['content'].encode()).hexdigest()
        files['config.json']['content'] = json.dumps(config, indent=2, allow_nan=False) + '\n'
        contract = json.loads(files['measurement-contract.json']['content'])
        contract['case_id'] = case_id
        contract['requirements'][0]['disposition_index'] = 4
        contract['requirements'][0]['output_key'] = 'paragraph_d_component_source_observation'
        files['measurement-contract.json']['content'] = json.dumps(contract, indent=2, allow_nan=False) + '\n'
        construction['recording_description']['limitations'].append(
            'This isolates an obstruction component of paragraph (d); one-way designation and actual clearance remain unreviewed.')
        directory = OUT / suffix
        path = directory / 'primary' / 'construction.json'
        put(path, construction)
        put(directory / 'measurement-contract.json', contract)
        entries.append({'case_id': case_id, 'kind': 'delivery',
            'construction': suffix + '/primary/construction.json',
            'construction_sha256': sha(path),
            'measurement_contract': suffix + '/measurement-contract.json',
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'candidate_risk': {'status': 'physical',
                'reason': 'Original one-way designation, obstruction and right pass remain unverified.'},
            'candidates': [],
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}})
    runtime = json.loads((ROOT / 'batch.json').read_text())['runtime']['root']
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': CASE.name,
        'runtime_manifest_sha256': sha(ROOT / runtime / 'SOURCE-MANIFEST.json'),
        'status': 'paragraph_d_component_cpu_draft_only', 'delivery_ready': False,
        'original_native_observed': False, 'cases': entries}
    put(OUT / 'manifest.json', manifest)
    return {'manifest_sha256': sha(OUT / 'manifest.json'),
            'construction_sha256': [item['construction_sha256'] for item in entries]}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
