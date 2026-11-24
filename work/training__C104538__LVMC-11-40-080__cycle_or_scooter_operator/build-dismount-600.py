"""Bind a separate dismount exception diagnostic to the same frozen cell."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.name + '__controlled_3'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    source = json.loads((HERE / 'draft-thirty-second-mounted-turn-primary-construction.json').read_text())
    construction = copy.deepcopy(source)
    construction['case_id'] = CASE
    construction['measurement_plan'] = {
        'method': 'source-bound dismount time, persistent walking-machine state, turn time, and later pedestrian-rule review',
        'status': 'synthetic_600_frame_cpu_diagnostic; original posture and pedestrian-rule conduct pending'}
    construction['mechanisms'].append('separate dismount-before-turn exception route and pedestrian-rule review')
    for part in construction['files']:
        if part['path'] == 'config.json':
            config = json.loads(part['content'])
            config['case_id'] = CASE
            config['selected_case_id'] = CASE
            config['supported_case_ids'] = [CASE]
            config['case'] = {'case_id': CASE}
            config['case_suffix'] = 'dismounted_turn'
            config['required_atoms'] = sorted(set(config['required_atoms']) | {
                'ru.pedestrian', 'kin.speed'})
            config['recording_description']['limitations'].append(
                'Pedestrian-rule compliance requires original walking route and signal review; synthetic posture rows are not physical proof')
            construction['recording_description'] = config['recording_description']
            part['content'] = json.dumps(config, indent=2) + '\n'
    target = HERE / 'draft-thirty-second-dismounted-turn-primary-construction.json'
    write(target, construction)
    contract = json.loads((HERE / 'v2-mounted-turn-measurement-contract.json').read_text())
    contract['case_id'] = CASE
    contract['requirements'][0]['disposition_index'] = 1
    contract['requirements'][0]['output_key'] = 'dismounted_turn_observation'
    contract['requirements'][0]['method'] = 'measure_dismounted_turn'
    contract['requirements'][0]['inputs'].extend(['trace.jsonl', 'approach.mkv'])
    contract_path = HERE / 'v2-dismounted-turn-measurement-contract.json'
    write(contract_path, contract)
    manifest_path = HERE / 'draft-thirty-second-execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    batch = json.loads((HERE.parents[1] / 'batch.json').read_text())
    manifest['runtime_manifest_sha256'] = batch['runtime']['source_manifest_sha256']
    entry = copy.deepcopy(next(e for e in manifest['cases'] if e['case_id'].endswith('__controlled_2')))
    entry['case_id'] = CASE
    entry['construction'] = target.name
    entry['construction_sha256'] = sha(target)
    entry['measurement_contract'] = contract_path.name
    entry['measurement_procedure']['output_schema'] = 'c104538-lvmc-synthetic-saved-dismount-diagnostic-v1-600'
    recipe = HERE / 'v2-dismounted-turn-primary-recipe.json'
    if recipe.is_file():
        entry['fixture_recipe'] = f'work/{HERE.name}/{recipe.name}'
    else:
        entry.pop('fixture_recipe', None)
    entry['candidates'] = []
    manifest['cases'] = [e for e in manifest['cases'] if e['case_id'] != CASE] + [entry]
    write(manifest_path, manifest)
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    if not any(e['case_id'] == CASE for e in plan['cases']):
        plan['cases'].append({
            'case_id': CASE, 'comparison_variable': 'dismount before governed U-turn',
            'kind': 'planned_only',
            'physical_target': 'dismount before turning, walk the bicycle through the turn, and obey pedestrian regulations',
            'requested_not_measured': True, 'selection_targets': ['full-train'],
            'source_branch': 'Express dismount exception to sign obedience',
            'target_law_id': 'LVMC-11-40-080'})
    exception = next(d for d in plan['requirement_dispositions'] if 'except' in d['branch'])
    exception['case_ids'] = [CASE]
    exception['status'] = 'selected_required'
    exception['evidence_or_gap'] = (
        'Separate controlled_3 600-frame synthetic source diagnostic requires dismount before turning and persistent walking-machine rows. '
        'Original rider posture, walking path, applicable pedestrian signals and compliance remain to be verified from source-bound Native records and pixels.')
    comparison_id = HERE.name + '__exception_comparison'
    if not any(c['comparison_id'] == comparison_id for c in plan['comparisons']):
        plan['comparisons'].append({
            'comparison_id': comparison_id,
            'case_ids': [HERE.name + '__controlled_2', CASE],
            'deliberate_differences': ['dismount before turn and walk the bicycle'],
            'fixed_conditions': ['frozen hill-crest U-turn cell', 'same no-U-turn approach sign',
                                 'same bicycle class, camera policy and 600-frame rate']})
    plan['source_scope_alternatives'] = {
        'selected': {'sign': 'no_u_turn', 'machine': 'bicycle', 'maneuver': 'u_turn'},
        'unselected_textual_alternatives': [
            {'sign': 'no_right_turn', 'reason': 'requires a right-turn maneuver outside frozen u_turn cell'},
            {'sign': 'no_left_turn', 'reason': 'requires a left-turn maneuver outside frozen u_turn cell'},
            {'machine': 'electric_bicycle', 'reason': 'same statutory mechanism but distinct physical machine outside selected bicycle witness'},
            {'machine': 'electric_scooter', 'reason': 'same statutory mechanism but distinct physical machine outside selected bicycle witness'}],
        'applicability_channels': ['dev.regulatory_sign', 'ru.bicycle',
                                   'ru.electric_bicycle', 'ru.electric_scooter']}
    alternatives = [
        ('no-right-turn sign', 'Requires a right-turn maneuver outside the frozen u_turn cell; compatible frozen binding or candidate cell remains to be constructed.'),
        ('no-left-turn sign', 'Requires a left-turn maneuver outside the frozen u_turn cell; compatible frozen binding or candidate cell remains to be constructed.'),
        ('electric-bicycle operator', 'Requires its own physical machine and controlled applicable-sign comparison; bicycle source does not establish this class.'),
        ('electric-scooter operator', 'Requires its own physical machine and controlled applicable-sign comparison; bicycle source does not establish this class.'),
    ]
    for branch, gap in alternatives:
        if not any(d['branch'] == branch for d in plan['requirement_dispositions']):
            plan['requirement_dispositions'].append({
                'branch': branch, 'case_ids': [], 'evidence_or_gap': gap,
                'requirement': 'LVMC-11-40-080', 'source': 'LVMC 11.40.080',
                'status': 'alternative_pending'})
    write(plan_path, plan)
    proposals_path = HERE / 'proposals/cases.json'
    proposals = json.loads(proposals_path.read_text())
    proposal = copy.deepcopy(next(e for e in proposals['cases'] if e['case_id'].endswith('__controlled_2')))
    proposal['case_id'] = CASE
    proposal['physical_target'] = 'dismount before the U-turn and walk the bicycle while following pedestrian rules'
    proposal['comparison_variable'] = 'dismount_before_turn'
    proposal['source_branch'] = 'Express dismount exception to sign obedience'
    proposal['controller']['requested_behavior'] = proposal['physical_target']
    proposal['variable_assignments'] = {
        'dismount_before_turn': {'kind': 'subject_behavior', 'value': None, 'unit': 'boolean'}}
    proposal['world_setup']['activation_conditions_to_verify'] = [
        'authorized no-U-turn sign governs bicycle approach',
        'rider dismounts before turning and walks the bicycle',
        'applicable pedestrian regulations are observed from original source']
    proposal['recording_description'] = construction['recording_description']
    proposals['cases'] = [e for e in proposals['cases'] if e['case_id'] != CASE] + [proposal]
    write(proposals_path, proposals)
    print(json.dumps({'construction_sha256': sha(target), 'contract_sha256': sha(contract_path),
                      'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
