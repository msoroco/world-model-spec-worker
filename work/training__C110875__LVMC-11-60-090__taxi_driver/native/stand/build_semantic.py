"""Write exact taxi-law semantic proposals without a legal verdict."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parents[1]
ROOT = HERE.parents[3]
ASSIGNMENT = FOLDER.name
LAW = 'LVMC-11-60-090'
ACTOR = 'taxi_driver'
TEMPLATE = LAW + '@' + ACTOR


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(FOLDER)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    source = json.loads((ROOT / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())
    exact = source['law']['text']
    relevance = {'cell_id': source['cell_id'], 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': exact, 'applies_to': [ACTOR],
            'relevance_type': 'specific_match', 'confidence': 'high',
            'notes': 'Original taxi license, designated stand, posted sign and first street identity need source review.'}],
        'borderline_excluded': []}
    refs = {}
    refs['relevance_batch'] = write(FOLDER / 'proposals/relevance-batch.json', relevance)
    refs['relevance'] = write(FOLDER / 'proposals/relevance.json', relevance)
    judgments = [
        {'phrase': 'stand designated in accordance with the provisions of this Section',
         'note': 'Confirm authority and physical stand boundary from independent source and original footage.'},
        {'phrase': 'when a sign is posted giving notice of this requirement',
         'note': 'Confirm sign face, posting and applicability from independent source and original footage.'},
        {'phrase': 'first street intersection after it leaves such stand',
         'note': 'Confirm ordered Native junction topology and public street identity from original recording.'}]
    proposal_path = FOLDER / 'proposals/cases.json'
    proposal = json.loads(proposal_path.read_text())
    proposal['status'] = 'draft'
    proposal['sweeps_expanded'] = True
    proposal['sweep_specs'] = [{
        'sweep_id': 'taxi-stand-notice-street-review', 'target_law_id': LAW,
        'judgment_refs': judgments, 'status': 'incomplete',
        'rationale': 'Independent designation, notice and street-identity review remains open while route observations are retained.',
        'missing_inputs': ['Original authority and sign-face review', 'Original public first-street identity review']}]
    for case in proposal['cases']:
        assignments = case['variable_assignments']
        if case['target_type'] == 'baseline':
            assignments['first_intersection_turn_direction'] = {'kind': 'subject_behavior', 'value': None}
            assignments['requested_first_turn'] = {'kind': 'controller', 'value': None}
        else:
            direction = assignments.get('requested_first_turn', {}).get('value')
            if direction is None:
                direction = case['target_type'].split('first_turn_')[-1]
            case['target_type'] = 'judgment_sweep'
            case['paired_probe_id'] = 'taxi_first_turn'
            case['deliberate_differences'] = ['requested_first_turn']
            case['probe'] = {'primary_variable': 'requested_first_turn',
                'comparison_or_standard': 'first street right-turn obligation with authority unresolved',
                'target_value_or_branch': direction}
            case['unresolved_judgment_calls'] = [item['phrase'] for item in judgments]
            assignments['first_intersection_turn_direction'] = {'kind': 'subject_behavior', 'value': None}
            assignments['requested_first_turn'] = {'kind': 'controller', 'value': direction}
        assignments['notice_posted'] = {'kind': 'world_setup',
            'value': 'authored right-turn notice; authority unverified'}
    proposal_path.write_text(json.dumps(proposal, indent=2) + '\n')
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR, 'status': 'draft',
        'quote': exact, 'structure': {
            'activation': {'description': 'A cab leaves a duly designated stand while a notice sign is posted.',
                'source_clause': 'Any cab, upon leaving any stand designated in accordance with the provisions of this Section'},
            'obligation': {'description': 'Observe the maneuver at the first street intersection after stand departure.',
                'type': 'must', 'source_clause': 'shall execute a right-hand turn'},
            'exceptions': [],
            'timing': {'description': 'Join stand departure, sign and first street intersection to original 20 Hz frames.'},
            'judgment_calls_needed': judgments},
        'parameter_refs': [
            {'name': 'first_intersection_turn_direction', 'kind': 'subject_behavior',
             'range_or_domain': 'observed right, straight, left or indeterminate'},
            {'name': 'notice_posted', 'kind': 'world_setup',
             'range_or_domain': 'source-reviewed posted notice or unresolved'}]}
    refs['template'] = write(FOLDER / 'proposals/template.json', template)
    observed = []
    units = {'ru.taxicab': 'identity', 'drv.turning': 'degrees',
             'kin.heading': 'degrees', 'kin.path_length': 'm'}
    for index, judgment in enumerate(judgments, 1):
        names = (['ru.taxicab', 'st.curb_zone'] if index == 1 else
                 ['dev.regulatory_sign', 'dev.governs'] if index == 2 else
                 ['st.intersection', 'drv.turning', 'kin.heading', 'kin.path_length'])
        requirements = {'observables': [{'name': name, 'unit': units.get(name, 'structured'),
            'description': 'Original synchronized source observation for ' + name} for name in names],
            'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [{'name': name, 'unit': units.get(name, 'structured'),
                'description': 'Retain original source and frame join for ' + name} for name in names],
            'limitations': ['Authority, street identity, physical realization and legal status remain unverified.']}
        observed.append(write(FOLDER / f'proposals/judgment-{index}.json',
            {'template_id': TEMPLATE, 'phrase': judgment['phrase'], 'note': judgment['note'],
             'status': 'draft', 'observable_requirements': requirements}))
    refs['judgment_observables'] = observed
    binding = {'cell_id': source['cell_id'], 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [], 'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [
            {'name': 'taxi_stand_context', 'value': 'frozen cell taxi stand', 'rationale': 'Frozen assignment cell.'}],
        'variable_parameters': [
            {'name': 'first_intersection_turn_direction', 'kind': 'subject_behavior',
             'range_or_domain': 'observed right, straight, left or indeterminate', 'used_by_laws': [LAW]},
            {'name': 'requested_first_turn', 'kind': 'controller',
             'range_or_domain': 'right or straight requested route', 'used_by_laws': [LAW]},
            {'name': 'notice_posted', 'kind': 'world_setup',
             'range_or_domain': 'source-reviewed posted notice or unresolved', 'used_by_laws': [LAW]}]}
    refs['bindings'] = write(FOLDER / 'proposals/bindings.json', binding)
    refs['cases'] = {'path': 'proposals/cases.json',
        'sha256': hashlib.sha256((FOLDER / 'proposals/cases.json').read_bytes()).hexdigest()}
    write(FOLDER / 'proposals/semantic-index.json',
          {'format': 'worker-semantic-delivery', 'assignment_id': ASSIGNMENT, 'stages': refs})
    print(json.dumps({'judgments': len(judgments), 'selected_cases': 2}))


if __name__ == '__main__':
    main()
