"""Select the two exact one-way travel definitions for CPU delivery preparation."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    path = HERE / 'case-plan.json'
    plan = json.loads(path.read_text())
    if len(plan['cases']) != 2 or {c['requested_setting'] for c in plan['cases']} != {'designated', 'opposite'}:
        raise ValueError('Frozen two-direction case plan differs')
    plan['selected_branch'] = 'designated and signposted one-way highway; compare travel along and opposed to its designated direction'
    for case in plan['cases']:
        case['selected'] = True
        case['planning_status'] = 'selected_cpu_construction_physical_unverified'
        case['kind'] = 'delivery'
        case['selection_targets'] = plan['selection_targets']
    for comparison in plan['comparisons']:
        comparison['status'] = 'selected_cpu_comparison_physical_unverified'
    plan['evidence_review'] = {
        'method': 'Reviewed frozen assignment membership rows and searched for an accepted evidence inventory; no evidence.json was supplied',
        'reviewer': 'worker source review', 'facts': [],
        'gaps': [{'id': 'one-way-direction-original', 'requirement': 'NRS-484B-220-1',
                  'source': 'inputs/' + HERE.name + '/assignment.json',
                  'why_existing_insufficient': 'Four demo/full membership rows lack source-hashed accepted recording evidence of one-way designation, physical signposting or original direction of travel'}]}
    for case in plan['cases']:
        case['gap_ids'] = ['one-way-direction-original']
    for term, mapping in plan['source_observation_mapping'].items():
        mapping['evidence'] = ('Selected source-bound acquisition: original Native pose, synchronized four-camera frame map, '
                               'OpenDRIVE readback and separately hashed one-way/sign review; original authority and pixels remain unverified until capture')
        if term == 'kin.heading':
            mapping['channels'] = ['ego_pose', 'kin.heading']
        elif term == 'rel.occupies':
            mapping['channels'] = ['ego_pose', 'rel.occupies']
        else:
            mapping['channels'] = ['travel_direction_vs_sign', term]
    plan['runtime_uncertainties'] = [
        'Exact 600-frame/four-camera selected Native construction is CPU checked; original Native execution and sign pixels remain unverified.',
        'Membership rows are not source-hashed accepted recording evidence.',
        'Independent road designation and official, erected, governing sign authority require original source review.',
        'Software compatibility, saved-only, semantic, delivery, physical and comparison proofs remain in progress.']
    path.write_text(json.dumps(plan, indent=2, allow_nan=False) + '\n')
    proposal = {'cell_id': 'C150916', 'actor': 'motor_vehicle_driver', 'status': 'draft',
                'sweep_specs': [], 'sweeps_expanded': True, 'cases': []}
    for case in plan['cases']:
        direction = case['requested_setting']
        construction = json.loads((HERE / 'selected' / 'drafts' / direction / 'primary' / 'construction.json').read_text())
        proposal['cases'].append({
            'case_id': case['case_id'], 'target_law_id': case['target_law_id'],
            'target_type': 'controlled_attempt', 'cell_id': 'C150916',
            'actor': 'motor_vehicle_driver', 'source_branch': plan['selected_branch'],
            'comparison_variable': 'travel_direction_vs_sign',
            'requested_not_measured': True,
            'variable_assignments': {'travel_direction_vs_sign': {'kind': 'controller',
                                                                   'value': direction, 'unit': 'category'}},
            'recording_description': construction['recording_description']})
    destination = HERE / 'proposals' / 'cases.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(proposal, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'selected_cases': [c['case_id'] for c in plan['cases']]}))


if __name__ == '__main__':
    main()
