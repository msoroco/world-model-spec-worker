"""Write source-grounded canonical draft stages for two school-zone attempts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
ASSIGNMENT = json.loads((ROOT.parents[1] / 'inputs' / AID / 'assignment.json').read_text())
LAW = ASSIGNMENT['law_id']
ACTOR = ASSIGNMENT['actor']
TEXT = ASSIGNMENT['law']['text']
TEMPLATE = LAW + '@' + ACTOR


def write(name, value):
    path = ROOT / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(ROOT)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    cases_path = ROOT / 'proposals/cases.json'
    cases = json.loads(cases_path.read_text())
    cases['cases'] = [case for case in cases['cases'] if case['target_type'] != 'baseline']
    construction = json.loads((ROOT / 'native/bundles/controlled_1/construction.json').read_text())
    description = construction['recording_description']
    judgments = [
        {'phrase': 'area designated as a school zone or school crossing zone',
         'note': 'Official designation and boundaries require independent source review.'},
        {'phrase': 'children present',
         'note': 'Identity and presence require independent original-source review.'},
        {'phrase': 'school is not in session',
         'note': 'Session day requires independent school records and civil time.'},
        {'phrase': 'school is no longer in operation',
         'note': 'Operation interval and statutory half hours require source review.'},
        {'phrase': 'operational speed limit beacon',
         'note': 'Beacon configuration, class hours and flashing state require source review.'},
        {'phrase': 'speed limit is not in effect',
         'note': 'Sign schedule and beacon condition require source review.'},
    ]
    relevance = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
                    'relevance_type': 'specific_match', 'confidence': 'high',
                    'notes': 'The frozen school-zone U-turn cell matches the statute; source review determines activation and exceptions.'}],
                 'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance-batch.json', relevance),
            'relevance': write('relevance.json', relevance)}
    clauses = [
        ('When there are no children present', 'Independent child-presence review supports this exception.'),
        ('On a day on which school is not in session', 'Independent session-day review supports this exception.'),
        ('During the period from a half hour after school is no longer in operation to a half hour before school is next in operation', 'Original operation and civil-time records support this exception.'),
        ('If the zone is designated by an operational speed limit beacon, during the hours when the pupils of the school are in class and the yellow lights of the speed limit beacon are not flashing in the manner which indicates that the speed limit is in effect', 'Original beacon, class-hour and light records support this exception.'),
        ('If the zone is not designated by an operational speed limit beacon, during the times when the sign designating the school zone or school crossing zone indicates that the speed limit is not in effect', 'Original beacon and sign records support this exception.'),
    ]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
        'status': 'draft', 'quote': TEXT,
        'structure': {'activation': {'condition': 'Vehicle driver makes a U-turn inside an officially designated school zone or school crossing zone.',
                                     'numeric_conditions': []},
            'obligation': {'description': 'Driver shall not make a U-turn in the designated zone unless a statutory exception applies.',
                           'type': 'must_not',
                           'source_clause': 'The driver of a vehicle shall not make a U-turn in an area designated as a school zone or school crossing zone',
                           'numeric_conditions': []},
            'exceptions': [{'source_clause': clause,
                            'trigger': trigger,
                            'effect': 'The section permits this U-turn when this exception applies.',
                            'replacement_obligation': 'Review all remaining applicable traffic duties separately.'}
                           for clause, trigger in clauses],
            'timing': {'description': 'Retain civil time, school session and operation, class hours, beacon lights and sign schedule across the attempt.',
                       'numeric_conditions': []},
            'judgment_calls_needed': judgments},
        'parameter_refs': [{'name': 'u_turn_request', 'kind': 'subject_behavior',
                            'range_or_domain': 'requested turn versus continuation; observed trajectory remains separate'},
                           {'name': 'commanded_turn_path', 'kind': 'controller',
                            'range_or_domain': 'authored physical path target, not a legal conclusion'},
                           {'name': 'school_zone_context', 'kind': 'world_setup',
                            'range_or_domain': 'official designation, child and school records, beacon and sign state'}]}
    refs['template'] = write('template.json', template)
    refs['judgment_observables'] = []
    for index, judgment in enumerate(judgments, 1):
        needs = [{'name': channel['name'], 'unit': channel['unit'],
                  'description': 'Retain original frame and source hash for ' + channel['name']}
                 for channel in description['channels']]
        observable = {'observables': needs, 'context_inputs': [],
                      'sweep_dimensions': [], 'landmarks': [], 'recording_needs': needs,
                      'limitations': ['Legal application remains for independent source review.']}
        refs['judgment_observables'].append(write(f'judgment-{index}.json',
            {'template_id': TEMPLATE, 'phrase': judgment['phrase'], 'note': judgment['note'],
             'status': 'draft', 'observable_requirements': observable}))
    binding = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [], 'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [],
        'fixed_parameters': [{'name': 'cell_layout', 'value': 'school_zone',
                              'rationale': 'Frozen catalog cell.'}],
        'variable_parameters': [{'name': item['name'], 'kind': item['kind'],
                                 'range_or_domain': item['range_or_domain'], 'used_by_laws': [LAW]}
                                for item in template['parameter_refs']]}
    refs['bindings'] = write('bindings.json', binding)
    branch = {'source_clause': template['structure']['obligation']['source_clause'],
              'judgment_context': [{'phrase': item['phrase'], 'note': item['note'],
                                    'status': 'not_exercised',
                                    'reason': 'Original source and legal review remain unresolved.'}
                                   for item in judgments]}
    cases['status'] = 'draft'
    cases['sweep_specs'] = [{'sweep_id': 'school-zone-source-review-' + str(index),
                             'target_law_id': LAW, 'judgment_refs': [judgment],
                             'status': 'incomplete',
                             'rationale': 'Preserve original sources for independent physical and legal review.',
                             'missing_inputs': ['Original Native capture and independent source review.']}
                            for index, judgment in enumerate(judgments, 1)]
    cases['sweeps_expanded'] = True
    baseline = {'case_id': AID + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'rationale': 'Common source-review setup before a turn request.',
        'variable_assignments': {'u_turn_request': {'kind': 'subject_behavior', 'value': None},
                                 'commanded_turn_path': {'kind': 'controller', 'value': None},
                                 'school_zone_context': {'kind': 'world_setup', 'value': 'independent_review_pending'}},
        'unresolved_judgment_calls': [item['phrase'] for item in judgments],
        'recording_description': description}
    for case in cases['cases']:
        suffix = case['case_id'].rsplit('__', 1)[-1]
        case['target_type'] = 'compliant_attempt' if suffix == 'controlled_1' else 'violating_attempt'
        case['paired_probe_id'] = 'school_zone_u_turn_pair'
        case['deliberate_differences'] = ['commanded_turn_path']
        case['variable_assignments'] = {
            'u_turn_request': {'kind': 'subject_behavior', 'value': None},
            'commanded_turn_path': {'kind': 'controller', 'value': suffix},
            'school_zone_context': {'kind': 'world_setup', 'value': 'independent_review_pending'}}
        case['probe'] = {'primary_variable': 'commanded_turn_path',
                         'comparison_or_standard': 'NRS 484B.363(3) U-turn prohibition',
                         'target_value_or_branch': suffix}
        case['deterministic_branch'] = branch
        case['unresolved_judgment_calls'] = [item['phrase'] for item in judgments]
    cases['cases'].insert(0, baseline)
    refs['cases'] = write('cases.json', cases)
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': AID, 'stages': refs})
    print('semantic stages', 5 + len(judgments))


if __name__ == '__main__':
    main()
