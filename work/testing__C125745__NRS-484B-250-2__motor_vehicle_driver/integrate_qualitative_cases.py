"""Select the proved qualitative variants in the canonical CPU delivery plan.

Run from the repository root. Existing evidence remains hash bound to its old
construction until the affected commands are rerun; this script does not claim
that a newly selected case is delivery ready.
"""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STRAIGHT = HERE.name + '__stop_opposite_straight'
ABSENT = HERE.name + '__stop_ego_left_near_time_no_device'


def read(name):
    return json.loads((HERE / name).read_text())


def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    config = read('config.json')
    for case_id in (STRAIGHT, ABSENT):
        if case_id not in config['supported_case_ids']:
            config['supported_case_ids'].append(case_id)
    write('config.json', config)

    construction = read('construction.json')
    embedded = next(row for row in construction['files'] if row['path'] == 'config.json')
    assert embedded['source'] == str((HERE / 'config.json').relative_to(ROOT))
    embedded['content'] = (HERE / 'config.json').read_text()
    write('construction.json', construction)

    # The absent-device builder derives its config from the selected root config.
    from build_absent_device_case import build as build_absent
    build_absent()

    variants = {
        STRAIGHT: ('straight-construction.json', 'straight-diagnostic-recipe.json',
                   'stop_opposite_straight-primary-offline.log',
                   'stop_opposite_straight-primary-compatibility.json',
                   'stop_opposite_straight-primary-analysis.log',
                   'stop_opposite_straight-primary-negative.log',
                   'stop_opposite_straight-primary-saved.json',
                   'stop_opposite_left_turn'),
        ABSENT: ('absent-construction.json', 'absent-diagnostic-recipe.json',
                 'stop_no_device-primary-offline.log',
                 'stop_no_device-primary-compatibility.json',
                 'stop_no_device-primary-analysis.log',
                 'stop_no_device-primary-negative.log',
                 'stop_no_device-primary-saved.json',
                 'stop_ego_left_near_time'),
    }
    proposal = read('proposals/cases.json')
    plan = read('case-plan.json')
    manifest = read('execution-manifest.json')
    by_case = {entry['case_id']: entry for entry in manifest['cases']}
    by_proposal = {entry['case_id']: entry for entry in proposal['cases']}
    for case_id, (construction_name, recipe, offline_log, compat, analysis_log,
                  negative_log, saved, reference) in variants.items():
        source = HERE / construction_name
        exact = read(construction_name)
        reference_id = HERE.name + '__' + reference
        reference_proposal = copy.deepcopy(by_proposal[reference_id])
        reference_proposal['case_id'] = case_id
        reference_proposal['recording_description'] = exact['recording_description']
        reference_proposal['target_type'] = 'boundary_probe'
        reference_proposal['paired_probe_id'] = (
            'qualitative_turn_intent' if case_id == STRAIGHT else 'qualitative_device_presence')
        reference_proposal['rationale'] = (
            'Opposite-direction other vehicle commands a straight exit at the same crossing; actual motion and exception judgment remain unresolved.'
            if case_id == STRAIGHT else
            'Ego entrance has no Native device in the synthetic construction; actual absence and official status remain unresolved.')
        reference_proposal['deliberate_differences'] = [
            'other vehicle straight rather than left-turn exit intent'
            if case_id == STRAIGHT else 'ego entrance device presence absent rather than stop sign present']
        variables = reference_proposal['variable_assignments']
        if case_id == STRAIGHT:
            variables['opposite_direction_left_turn']['value'] = False
            variables['commanded_turn_path']['value'] = 'opposite_straight_waypoints'
        else:
            variables['native_stop_sign_id']['value'] = None
            variables['official_device_status']['value'] = 'no Native entrance device commanded; official status unverified'
        if case_id not in by_proposal:
            proposal['cases'].append(reference_proposal)

        if case_id not in {row['case_id'] for row in plan['cases']}:
            plan['cases'].append({
                'case_id': case_id, 'target_law_id': plan['law_id'],
                'purpose': reference_proposal['rationale'],
                'physical_risk': ('Native route geometry and observed turn intent need capture'
                                  if case_id == STRAIGHT else
                                  'Native map may have a baked entrance device'),
                'qualified_construction': construction_name,
                'qualified_construction_sha256': sha(source)})
        else:
            row = next(row for row in plan['cases'] if row['case_id'] == case_id)
            row['qualified_construction_sha256'] = sha(source)

        for disposition in plan['requirement_dispositions']:
            if case_id not in disposition['case_ids']:
                disposition['case_ids'].append(case_id)
        if case_id not in by_case:
            manifest['cases'].append({
                'case_id': case_id, 'kind': 'delivery',
                'construction': construction_name,
                'construction_sha256': sha(source),
                'physical_risk': {'status': 'physical', 'reason':
                    'Native motion, source visibility and legal judgment require later capture'},
                'candidates': [],
                'measurement_contract': 'measurement-contract.json',
                'measurement_procedure': {'entrypoint': 'finalizer.py'},
                'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
                'fixture_recipe': str((HERE / recipe).relative_to(ROOT))})
        else:
            by_case[case_id]['construction_sha256'] = sha(source)

    first = by_case[HERE.name + '__stop_ego_left_near_time']
    first['construction_sha256'] = sha(HERE / 'construction.json')
    for name, cases, difference in (
        ('stop_sign_opposite_turn_intent',
         ('stop_opposite_left_turn', 'stop_opposite_straight'),
         'other commanded left-turn versus straight exit while approach and entry timing remain fixed'),
        ('stop_sign_entrance_device_presence',
         ('stop_ego_left_near_time', 'stop_ego_left_near_time_no_device'),
         'sourced Native entrance sign present versus absent while crossing and entry timing remain fixed')):
        if name not in {row['comparison_id'] for row in plan['comparisons']}:
            plan['comparisons'].append({
                'comparison_id': name,
                'case_ids': [HERE.name + '__' + suffix for suffix in cases],
                'fixed_conditions': ['same synthetic crossing, actors, entrance paths, entry timing and four-camera capture'],
                'deliberate_differences': [difference]})
    write('proposals/cases.json', proposal)
    write('case-plan.json', plan)
    write('execution-manifest.json', manifest)
    print(json.dumps({'selected_cases': [STRAIGHT, ABSENT],
                      'manifest_sha256': sha(HERE / 'execution-manifest.json'),
                      'first_construction_sha256': first['construction_sha256'],
                      'new_proofs_needed': True}, sort_keys=True))


if __name__ == '__main__':
    main()
