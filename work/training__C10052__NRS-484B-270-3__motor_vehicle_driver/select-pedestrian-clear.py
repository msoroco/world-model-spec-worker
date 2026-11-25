"""Bind the constructed pedestrian clear diagnostic to the selected manifest."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__pedestrian_clear'
SELECTED = ROOT / 'selected-pedestrian-clear'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def replace(value):
    if isinstance(value, str):
        return value.replace('rider_bicycle_clear', 'pedestrian_clear').replace('ru.bicycle', 'ru.pedestrian').replace('rider', 'pedestrian')
    if isinstance(value, list):
        return [replace(item) for item in value]
    if isinstance(value, dict):
        return {replace(k): replace(v) for k, v in value.items()}
    return value


def main():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    draft = json.loads((ROOT / 'draft-pedestrian-execution-manifest.json').read_text())
    entry = next(row for row in draft['cases'] if row['case_id'] == CASE)
    entry['kind'] = 'delivery'
    entry['construction'] = 'selected-pedestrian-clear/primary/construction.json'
    entry['construction_sha256'] = sha(SELECTED / 'primary/construction.json')
    entry['candidates'] = [row for row in entry['candidates'] if row['id'] in ('fallback1', 'fallback2')]
    for row in entry['candidates']:
        row['construction'] = f"selected-pedestrian-clear/{row['id']}/construction.json"
        row['construction_sha256'] = sha(SELECTED / row['id'] / 'construction.json')
    entry['fixture_recipe'] = str((SELECTED / 'fixture-recipe.json').relative_to(REPO))
    entry['measurement_contract'] = 'selected-pedestrian-clear/measurement-contract.json'
    entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
    bicycle = next(row for row in manifest['cases'] if row['case_id'].endswith('__rider_bicycle_clear'))
    entry['acquisition'] = replace(bicycle['acquisition'])
    write(SELECTED / 'measurement-contract.json', {
        'format': 'worker-measurement-contract', 'case_id': CASE,
        'requirements': [{'disposition_index': 0, 'requirement': 'NRS-484B-270-3',
                          'source': 'NRS 484B.270(3)', 'output_key': 'pedestrian_conflict_observation',
                          'method': 'finalize', 'value_type': 'object', 'kind': 'measured',
                          'inputs': ['pedestrian_native_samples.jsonl', 'pedestrian_geometry.json',
                                     'pedestrian-source-manifest.json']}],
        'negative': {'remove': ['pedestrian-source-manifest.json'],
                     'error_contains': 'Missing required source: pedestrian-source-manifest.json'}})
    manifest['cases'] = [row for row in manifest['cases'] if row['case_id'] != CASE] + [entry]
    write(manifest_path, manifest)
    proposal_path = ROOT / 'proposals/cases.json'
    proposals = json.loads(proposal_path.read_text())
    base = next(row for row in proposals['cases'] if row['case_id'].endswith('__rider_bicycle_clear'))
    proposed = replace(base)
    proposed['case_id'] = CASE
    proposed['recording_description'] = json.loads((SELECTED / 'primary/construction.json').read_text())['recording_description']
    proposals['cases'] = [row for row in proposals['cases'] if row['case_id'] != CASE] + [proposed]
    write(proposal_path, proposals)
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    disposition = plan['requirement_dispositions'][0]
    if CASE not in disposition['case_ids']:
        disposition['case_ids'].append(CASE)
    case = next(row for row in plan['cases'] if row['case_id'] == CASE)
    case['kind'] = 'delivery'
    case['planning_status'] = 'selected_v2_compatibility_pending'
    case['candidate_plans'] = [row for row in case['candidate_plans'] if row['id'] in ('primary', 'fallback1', 'fallback2')]
    write(plan_path, plan)
    print(json.dumps({'case_id': CASE, 'selected': True, 'source_frames': 600}))


if __name__ == '__main__':
    main()
