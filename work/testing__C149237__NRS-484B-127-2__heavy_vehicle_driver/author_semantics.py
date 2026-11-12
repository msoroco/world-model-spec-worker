"""Author source-bound draft semantic proposals for the truck-following assignment."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = json.loads((ROOT.parents[1] / 'inputs' / ROOT.name / 'assignment.json').read_text())
PROPOSALS = ROOT / 'proposals'
LAW_ID = ASSIGNMENT['law_id']
ACTOR = ASSIGNMENT['actor']
TEMPLATE_ID = f'{LAW_ID}@{ACTOR}'
QUOTE = ASSIGNMENT['law']['text']


def write(name, value):
    path = PROPOSALS / name
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': f'proposals/{name}', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def variable(name, kind, domain):
    return {'name': name, 'kind': kind, 'range_or_domain': domain}


def observation(phrase, note, observable, description):
    return {'template_id': TEMPLATE_ID, 'phrase': phrase, 'note': note, 'status': 'draft',
            'observable_requirements': {
                'observables': [{'name': observable, 'unit': 'm', 'description': description}],
                'context_inputs': [{'name': 'conditions_permitting', 'unit': 'source review',
                                    'description': 'Native road, traffic, and camera review with unresolved judgment'}],
                'sweep_dimensions': [{'name': observable, 'unit': 'm', 'description': description}],
                'landmarks': [],
                'recording_needs': [{'name': observable, 'unit': 'm', 'description': description}],
                'limitations': ['A sampled body gap cannot settle road conditions, overtaker safety, or legal applicability.']}}


def main():
    PROPOSALS.mkdir(exist_ok=True)
    relevance = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW_ID, 'quote': QUOTE, 'applies_to': [ACTOR],
                                    'relevance_type': 'direct selected truck-following duty',
                                    'confidence': 'high',
                                    'notes': 'Width, following, roadway exception, and conditions still need original Native review.'}],
                 'borderline_excluded': []}
    relevant = write('relevance.json', relevance)
    batch = write('relevance-batch.json', relevance)
    params = [variable('requested_body_gap_m', 'world_setup', 'positive engineering metres'),
              variable('ego_target_speed_mps', 'controller', 'positive engineering m/s'),
              variable('lead_target_speed_mps', 'controller', 'positive engineering m/s'),
              variable('same_direction_lane_count', 'world_setup', 'positive integer'),
              variable('requested_ego_width_m', 'world_setup', 'engineering candidate width in metres'),
              variable('requested_lead_width_m', 'world_setup', 'engineering candidate width in metres'),
              variable('passing_lane_id', 'world_setup', 'engineering lane identifier for pass exception'),
              variable('longitudinal_body_gap', 'subject_behavior', 'observed metres; never commanded'),
              variable('ego_overall_width', 'subject_behavior', 'observed metres; never commanded'),
              variable('lead_overall_width', 'subject_behavior', 'observed metres; never commanded')]
    judgments = [
        {'phrase': 'whenever conditions permit', 'note': 'Road, traffic, visibility, and continuity require original-source review.'},
        {'phrase': 'without danger', 'note': 'Safe entry and occupancy by an overtaking vehicle require original-source review.'}]
    template = {'template_id': TEMPLATE_ID, 'law_id': LAW_ID, 'actor': ACTOR, 'status': 'draft',
                'quote': QUOTE, 'structure': {'law_id': LAW_ID,
                    'activation': {'condition': 'Ego is a truck or combination at least 80 inches overall and follows a truck or combination at least 80 inches overall.',
                                   'numeric_conditions': [
                                       {'variable': 'ego_overall_width', 'operator': '>=', 'value': 80, 'unit': 'in'},
                                       {'variable': 'lead_overall_width', 'operator': '>=', 'value': 80, 'unit': 'in'}]},
                    'obligation': {'description': 'Whenever conditions permit, leave 500 feet so an overtaking vehicle may enter and occupy the space without danger.',
                                   'type': 'must', 'numeric_conditions': [
                                       {'variable': 'longitudinal_body_gap', 'operator': '>=', 'value': 500, 'unit': 'ft'}]},
                    'exceptions': [
                        {'source_clause': 'but this shall not prevent a truck or combination of vehicles from overtaking and passing any vehicle or combination of vehicles',
                         'description': 'Overtaking and passing remains permitted.'},
                        {'source_clause': 'This subsection does not apply to any vehicle or combination of vehicles while moving on a highway on which there are two or more lanes available for traffic moving in the same direction.',
                         'description': 'Two or more same-direction lanes on a highway exclude this subsection.'}],
                    'timing': {'description': 'While the qualifying following relation and conditions persist.', 'numeric_conditions': []},
                    'judgment_calls_needed': judgments}, 'parameter_refs': params}
    template_ref = write('template.json', template)
    observed = [write('judgment-conditions.json', observation(judgments[0]['phrase'], judgments[0]['note'],
                'longitudinal_body_gap', 'Sampled complete-body separation through the following interval.')),
                write('judgment-danger.json', observation(judgments[1]['phrase'], judgments[1]['note'],
                'longitudinal_body_gap', 'Sampled complete-body separation available for overtaker entry.'))]
    binding = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR, 'status': 'draft',
               'established_contexts': ['Frozen truck-following cell; physical width and highway status await original-source review.'],
               'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}], 'context_refs': [],
               'fixed_parameters': [{'name': 'selected_cell', 'value': ASSIGNMENT['cell_id'], 'rationale': 'Frozen assignment cell.'}],
               'variable_parameters': [dict(p, used_by_laws=[LAW_ID]) for p in params]}
    binding_ref = write('bindings.json', binding)
    cases_ref = {'path': 'proposals/cases.json', 'sha256': hashlib.sha256((PROPOSALS / 'cases.json').read_bytes()).hexdigest()}
    write('semantic-index.json', {'format': 'worker-semantic-delivery', 'assignment_id': ROOT.name,
          'stages': {'relevance_batch': batch, 'relevance': relevant, 'template': template_ref,
                     'judgment_observables': observed, 'bindings': binding_ref, 'cases': cases_ref}})


if __name__ == '__main__':
    main()
