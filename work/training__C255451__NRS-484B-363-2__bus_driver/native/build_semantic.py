"""Author the six canonical stage proposals for the exact school-crossing clause."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
ASSIGNMENT = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']
ACTOR = ASSIGNMENT['actor']
CELL = ASSIGNMENT['cell_id']
LAW_ID = ASSIGNMENT['law_id']
PROPOSALS = ROOT / 'proposals'


def save(name, value):
    path = PROPOSALS / (name + '.json')
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    relevance = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW_ID, 'quote': LAW['text'],
                                    'applies_to': [ACTOR], 'relevance_type': 'specific_match',
                                    'confidence': 'high',
                                    'notes': 'Motor bus in a designated school crossing zone; original authority, child, schedule and sign sources require review.'}],
                 'borderline_excluded': []}
    relevance_batch = save('relevance_batch', relevance)
    relevance_single = save('relevance', relevance)
    template_id = LAW_ID + '@' + ACTOR
    exception_phrases = [
        'On a day on which school is not in session',
        'During the period from a half hour after school is no longer in operation to a half hour before school is next in operation',
        'If the zone is designated by an operational speed limit beacon, during the hours when the pupils of the school are in class and the yellow lights of the speed limit beacon are not flashing in the manner which indicates that the speed limit is in effect',
        'If the zone is not designated by an operational speed limit beacon, during the times when the sign designating the school zone indicates that the speed limit is not in effect',
    ]
    descriptions = [
        'Review the original school calendar and exact local day.',
        'Review operation schedule and time-zone-aware civil clock at both half-hour boundaries.',
        'Review operational beacon designation, class hours, sign and two alternating yellow lights.',
        'Review absence of operational beacon and original sign schedule and indication.',
    ]
    template = {'template_id': template_id, 'law_id': LAW_ID, 'actor': ACTOR,
                'status': 'draft', 'quote': LAW['text'],
                'structure': {
                    'activation': {'source_clause': 'in an area designated as a school crossing zone',
                                   'description': 'Original authority for designation, installed sign, zone boundaries and bus route.'},
                    'obligation': {'source_clause': 'shall not drive a motor vehicle at a speed in excess of 25 miles per hour',
                                   'type': 'must_not',
                                   'description': 'Measure original Native motor-bus speed inside the designated crossing zone.',
                                   'numeric_conditions': [{'variable': 'observed_bus_speed_mph', 'operator': '>',
                                                           'value': 25, 'unit': 'mph'}]},
                    'exceptions': [{'source_clause': phrase, 'trigger': phrase,
                                    'effect': '25 mph school-crossing-zone exception subject to original-source review',
                                    'replacement_obligation': None, 'description': description}
                                   for phrase, description in zip(exception_phrases, descriptions)],
                    'timing': {'source_clause': 'during the hours when the pupils of the school are in class',
                               'description': 'Review local school calendar, operating windows and time-zone-aware civil clock.'},
                    'judgment_calls_needed': []},
                'parameter_refs': []}
    template_ref = save('template', template)
    bindings = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                'established_contexts': [],
                'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
                'context_refs': [], 'fixed_parameters': [],
                'variable_parameters': [
                    {'name': 'requested_bus_speed_mph', 'kind': 'controller',
                     'range_or_domain': '20, 25 or 30 mph engineering requests; actual speed independently measured',
                     'used_by_laws': [LAW_ID]},
                    {'name': 'reviewed_school_context', 'kind': 'controller',
                     'range_or_domain': 'designation, calendar, clock, operational beacon, alternating yellow lights and sign',
                     'used_by_laws': [LAW_ID]},
                    {'name': 'observed_bus_speed_mph', 'kind': 'subject_behavior',
                     'range_or_domain': 'original Native velocity samples inside reviewed zone; unknown before capture',
                     'used_by_laws': [LAW_ID]}]}
    binding_ref = save('bindings', bindings)
    cases = PROPOSALS / 'cases.json'
    case_proposal = json.loads(cases.read_text())
    for item in case_proposal['cases']:
        if item.get('target_type') == 'baseline':
            continue
        condition = item['case_id'].rsplit('__', 1)[-1]
        speed_probe = condition in ('condition_a', 'at_limit', 'condition_b')
        item['paired_probe_id'] = 'school_crossing_25_mph_boundary' if speed_probe else 'school_crossing_exception_contexts'
        item['deliberate_differences'] = ['requested_bus_speed_mph'] if speed_probe else ['reviewed_school_context']
        item['probe'] = {
            'primary_variable': 'observed_bus_speed_mph' if speed_probe else 'reviewed_school_context',
            'comparison_or_standard': 'exact statutory 25 mph limit when active' if speed_probe else 'original-source-reviewed statutory exception context',
            'target_value_or_branch': {'condition_a': 'below', 'at_limit': 'at', 'condition_b': 'above'}.get(condition, condition),
        }
        if speed_probe:
            item['probe'].update({'threshold_ref': 'obligation.numeric_conditions[0]',
                                  'operator': '>', 'unit': 'mph',
                                  'test_value': {'condition_a': 20, 'at_limit': 25, 'condition_b': 30}[condition]})
            item['epsilon_used'] = {'value': 5, 'unit': 'mph',
                                    'rationale': 'Engineering spacing for requested speed; no legal tolerance or achieved speed is implied.'}
    if not any(case.get('target_type') == 'baseline' for case in case_proposal['cases']):
        baseline = deepcopy(case_proposal['cases'][0])
        baseline['case_id'] = ROOT.name + '__semantic_baseline'
        baseline['target_law_id'] = None
        baseline['target_type'] = 'baseline'
        baseline['rationale'] = 'Unselected reference for the source-bound school crossing comparison; no extra recording.'
        baseline['unresolved_judgment_calls'] = []
        case_proposal['cases'].insert(0, baseline)
    cases.write_text(json.dumps(case_proposal, indent=2, ensure_ascii=False) + '\n')
    case_ref = {'path': str(cases.relative_to(ROOT)), 'sha256': hashlib.sha256(cases.read_bytes()).hexdigest()}
    index = {'format': 'worker-semantic-delivery', 'assignment_id': ROOT.name,
             'stages': {'relevance_batch': relevance_batch, 'relevance': relevance_single,
                        'template': template_ref, 'judgment_observables': [],
                        'bindings': binding_ref, 'cases': case_ref}}
    save('semantic-index', index)
    return index


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
