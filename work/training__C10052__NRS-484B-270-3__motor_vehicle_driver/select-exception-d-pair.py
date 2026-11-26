"""Bind selected synthetic exception D pair and source contracts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def replace(value, response):
    if isinstance(value, str):
        return value.replace('rider_bicycle_clear', 'exception_d_' + response)
    if isinstance(value, list):
        return [replace(item, response) for item in value]
    if isinstance(value, dict):
        return {replace(k, response): replace(v, response) for k, v in value.items()}
    return value


def main():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    draft = json.loads((ROOT / 'draft-exception-d-execution-manifest.json').read_text())
    proposal_path = ROOT / 'proposals/cases.json'
    proposals = json.loads(proposal_path.read_text())
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    base = next(row for row in manifest['cases'] if row['case_id'].endswith('__rider_bicycle_clear'))
    base_proposal = next(row for row in proposals['cases'] if row['case_id'].endswith('__rider_bicycle_clear'))
    for response in ('duty', 'routine'):
        case = ROOT.name + '__exception_d_' + response
        selected = ROOT / ('selected-exception-d-' + response)
        entry = next(row for row in draft['cases'] if row['case_id'] == case)
        entry['kind'] = 'delivery'
        entry['construction'] = f'selected-exception-d-{response}/primary/construction.json'
        entry['construction_sha256'] = sha(selected / 'primary/construction.json')
        for row in entry['candidates']:
            row['construction'] = f"selected-exception-d-{response}/{row['id']}/construction.json"
            row['construction_sha256'] = sha(selected / row['id'] / 'construction.json')
        entry['fixture_recipe'] = str((selected / 'fixture-recipe.json').relative_to(REPO))
        entry['measurement_contract'] = f'selected-exception-d-{response}/measurement-contract.json'
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        entry['acquisition'] = base['acquisition']
        write(selected / 'measurement-contract.json', {
            'format': 'worker-measurement-contract', 'case_id': case,
            'requirements': [{'disposition_index': 0, 'requirement': 'NRS-484B-270-3',
                              'source': 'NRS 484B.270(3)', 'output_key': 'exception_d_observation',
                              'method': 'finalize', 'value_type': 'object', 'kind': 'measured',
                              'inputs': ['exception_d_native_samples.jsonl', 'duty-assignment.json', 'road_geometry.json',
                                         'exception-d-source-manifest.json']}],
            'negative': {'remove': ['exception-d-source-manifest.json'],
                         'error_contains': 'Missing required source: exception-d-source-manifest.json'}})
        manifest['cases'] = [row for row in manifest['cases'] if row['case_id'] != case] + [entry]
        proposed = replace(base_proposal, response)
        proposed['case_id'] = case
        proposed['recording_description'] = json.loads((selected / 'primary/construction.json').read_text())['recording_description']
        proposals['cases'] = [row for row in proposals['cases'] if row['case_id'] != case] + [proposed]
        case_plan = next(row for row in plan['cases'] if row['case_id'] == case)
        case_plan['kind'] = 'delivery'
        case_plan['planning_status'] = 'selected_v2_compatibility_pending'
        if case not in plan['requirement_dispositions'][0]['case_ids']:
            plan['requirement_dispositions'][0]['case_ids'].append(case)
    write(manifest_path, manifest)
    write(proposal_path, proposals)
    write(plan_path, plan)
    print('selected exception D pair bound')


if __name__ == '__main__':
    main()
