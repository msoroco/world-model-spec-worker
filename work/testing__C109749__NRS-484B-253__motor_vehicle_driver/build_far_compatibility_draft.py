"""Build an isolated exact far-case compatibility workspace.

This keeps the canonical eleven-case manifest, plan and proposal unchanged.
The diagnostic is synthetic source-shaped software evidence only.
"""
import copy
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
CASE = 'testing__C109749__NRS-484B-253__motor_vehicle_driver__approaching_far'
BASE = 'testing__C109749__NRS-484B-253__motor_vehicle_driver__approaching_no_yield'
SOURCE = FOLDER / 'cases/approaching_no_yield/diagnostic.json'
DRAFT = FOLDER / 'far-draft'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    DRAFT.mkdir(exist_ok=True)
    source = copy.deepcopy(json.loads(SOURCE.read_text()))
    rows = [json.loads(line) for line in source['files']['interaction_history.jsonl'].splitlines() if line]
    for row in rows:
        actor = row['oncoming']
        actor['position_xy_m'][0] += 20
        actor['velocity_xy_mps'] = [-1.0, 0.0]
        for vertex in actor['body_vertices_xy_m']:
            vertex[0] += 20
    source['files']['interaction_history.jsonl'] = ''.join(
        json.dumps(row, separators=(',', ':')) + '\n' for row in rows)
    provenance = json.loads(source['files']['fixture-provenance.json'])
    provenance['scope'] = ('C109749 far-approach nine-frame synthetic compatibility diagnostic; '
                           'not physical or legal evidence')
    provenance['case_specific_sources'] = ['intersection_geometry.json',
                                           'interaction_history.jsonl']
    source['files']['fixture-provenance.json'] = json.dumps(provenance, indent=2) + '\n'
    diagnostic = FOLDER / 'cases/approaching_far/diagnostic.json'
    # Graph-heavy text must stay below the worker's per-file return limit.
    diagnostic.write_text(json.dumps(source, separators=(',', ':'),
                                     ensure_ascii=False) + '\n')
    rel = str(diagnostic.relative_to(REPO))
    write(FOLDER / 'cases/approaching_far/diagnostic-recipe.json', {
        'format': 'worker-fixture-recipe', 'sources': [
            {'path': 'diagnostic-input.json', 'source': rel, 'sha256': sha(diagnostic)}],
        'generator': {'source': rel, 'sha256': sha(diagnostic)}})
    draft_manifest = json.loads((FOLDER / 'cases/approaching_far/draft-manifest.json').read_text())
    item = draft_manifest['cases'][0]
    for name in ('construction.json', 'fallback1-construction.json',
                 'fallback2-construction.json', 'fallback3-construction.json'):
        (DRAFT / name).write_bytes((FOLDER / 'cases/approaching_far' / name).read_bytes())
    (DRAFT / 'measurement-contract.json').write_bytes(
        (FOLDER / 'cases/approaching_far/measurement-contract.json').read_bytes())
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    for disposition in plan['requirement_dispositions']:
        if disposition['status'] == 'selected_required':
            disposition['case_ids'].append(CASE)
    write(DRAFT / 'case-plan.json', plan)
    proposal = json.loads((FOLDER / 'proposals/cases.json').read_text())
    base = next(row for row in proposal['cases'] if row['case_id'] == BASE)
    new = copy.deepcopy(base)
    new['case_id'] = CASE
    new['rationale'] = ('Measured distant opposing body remains outside through subject turn start; '
                        'time to conflict is an engineering observation, not a legal hazard cutoff.')
    new['variable_assignments']['subject_yield_policy']['value'] = False
    new['variable_assignments']['controller_release_ttc_s']['value'] = 4.0
    new['paired_probe_id'] = 'c109749-far-approach-engineering-sweep'
    new['deliberate_differences'] = ['opposing_distance_at_turn',
                                     'oncoming_closing_speed_mps', 'subject_control_policy']
    new['probe']['primary_variable'] = 'opposing_distance_at_turn'
    new['probe']['target_value_or_branch'] = ('Subject turn starts before an opposing complete body '
                                               'enters the junction, with measured TTC above the '
                                               'engineering release setting.')
    proposal['cases'].append(new)
    write(DRAFT / 'proposals/cases.json', proposal)
    root_manifest = json.loads((FOLDER / 'execution-manifest.json').read_text())
    entry = {'case_id': CASE, 'kind': 'delivery',
             'construction': 'construction.json',
             'construction_sha256': item['construction_sha256'],
             'measurement_procedure': {'entrypoint': 'finalizer.py'},
             'measurement_contract': 'measurement-contract.json',
             'fixture_recipe': str((FOLDER / 'cases/approaching_far/diagnostic-recipe.json').relative_to(REPO)),
             'candidate_risk': item['candidate_risk'],
             'candidates': item['candidates'],
             'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}}
    write(DRAFT / 'execution-manifest.json', {
        'format': 'worker-execution-manifest',
        'assignment_id': FOLDER.name,
        'runtime_manifest_sha256': root_manifest['runtime_manifest_sha256'],
        'cases': [entry]})
    print(json.dumps({'case_id': CASE, 'diagnostic_sha256': sha(diagnostic),
                      'manifest_sha256': sha(DRAFT / 'execution-manifest.json'),
                      'canonical_selection_modified': False}))


if __name__ == '__main__':
    main()
