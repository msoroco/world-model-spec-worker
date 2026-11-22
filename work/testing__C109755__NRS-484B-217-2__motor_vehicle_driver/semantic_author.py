"""Author source-bound canonical CPU stage proposals for this exact assignment."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = json.loads((ROOT.parents[1] / 'inputs' / ROOT.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']['text']
LAW_ID = ASSIGNMENT['law_id']
CELL = ASSIGNMENT['cell_id']
ACTOR = ASSIGNMENT['actor']
TEMPLATE_ID = LAW_ID + '@' + ACTOR
PROPOSALS = ROOT / 'proposals'


def write(name, value):
    path = PROPOSALS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def observed(name, unit, description):
    return {'name': name, 'unit': unit, 'description': description}


def channel(name, method):
    return {'name': name, 'unit': 'structured record', 'sampling_rate_hz': 20,
            'method': method, 'time_window': 'entire approach and left turn',
            'reference_frame': 'CARLA world with source frame and time',
            'uncertainty': '20 Hz sampling and simulator geometry precision'}


def context(name, method):
    return {'name': name, 'unit': 'structured record', 'method': method}


def main():
    relevance = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW_ID, 'quote': LAW,
                                    'applies_to': [ACTOR], 'relevance_type': 'direct left-turn crossing',
                                    'confidence': 'high',
                                    'notes': 'The cell specifies an intersection left turn with pavement striping; actual zone and exceptions remain to be verified.'}],
                 'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance_batch.json', relevance),
            'relevance': write('relevance.json', relevance)}
    clauses = [
        'Except as otherwise provided in subsections 3 and 4',
        'A driver may drive across a pavement striping marking such zone to an adjoining highway if the driver has first given the appropriate turn signal and there will be no impediment to oncoming or following traffic.',
        'Except where otherwise provided, a driver may drive across a pavement striping marking such a zone to make a left-hand turn if the driver has first given the appropriate turn signal in compliance with NRS 484B.413 [NRS-484B-413-2], if it is safe and if it would not be an impediment to oncoming or following traffic.',
    ]
    judgments = [
        {'phrase': 'if it is safe', 'note': 'The law supplies no numeric safety boundary.'},
        {'phrase': 'if it would not be an impediment to oncoming or following traffic',
         'note': 'The law supplies no numeric impediment boundary.'},
    ]
    template = {'template_id': TEMPLATE_ID, 'law_id': LAW_ID, 'actor': ACTOR,
                'quote': LAW,
                'structure': {'law_id': LAW_ID,
                              'activation': {'condition': 'Driver encounters a marked no-passing zone or its marking on a highway.', 'numeric_conditions': []},
                              'obligation': {'description': 'Do not drive on the left side within the zone or across/on its marking throughout its length, subject to stated exceptions.',
                                             'type': 'must_not', 'numeric_conditions': []},
                              'exceptions': [
                                  {'trigger': 'Subsection 3 or 4 applies', 'effect': 'Base prohibition may be displaced', 'replacement_obligation': 'Resolve the applicable subsection from source evidence', 'source_clause': clauses[0]},
                                  {'trigger': 'Crossing to an adjoining highway', 'effect': 'Conditional crossing permission', 'replacement_obligation': 'Prior turn signal and no impediment to oncoming or following traffic', 'source_clause': clauses[1]},
                                  {'trigger': 'Crossing to make a left-hand turn', 'effect': 'Conditional crossing permission', 'replacement_obligation': 'Prior appropriate turn signal, safety, and no impediment to oncoming or following traffic', 'source_clause': clauses[2]},
                              ],
                              'timing': {'description': 'Appropriate turn signal must precede crossing the marking.', 'numeric_conditions': []},
                              'judgment_calls_needed': judgments},
                'parameter_refs': [
                    {'name': 'turn_signal_command', 'kind': 'controller', 'range_or_domain': 'on or off'},
                    {'name': 'commanded_turn_path', 'kind': 'controller', 'range_or_domain': 'left turn across marking'},
                    {'name': 'oncoming_gap_setup', 'kind': 'world_setup', 'range_or_domain': 'physical initial spacing in m'},
                    {'name': 'following_gap_setup', 'kind': 'world_setup', 'range_or_domain': 'physical initial spacing in m'},
                ]}
    refs['template'] = write('template.json', template)
    observable_refs = []
    for judgment in judgments:
        impediment = 'impediment' in judgment['phrase']
        needs = ([observed('oncoming_history', 'structured record', 'Original oncoming trajectory and body footprint.'),
                  observed('following_history', 'structured record', 'Original following trajectory and body footprint.')]
                 if impediment else [observed('ego_body_history', 'structured record', 'Original ego trajectory and body footprint.'),
                                     observed('oncoming_history', 'structured record', 'Original oncoming trajectory and body footprint.'),
                                     observed('following_history', 'structured record', 'Original following trajectory and body footprint.')])
        entry = {'template_id': TEMPLATE_ID, 'phrase': judgment['phrase'], 'note': judgment['note'],
                 'status': 'draft', 'observable_requirements': {
                     'observables': needs,
                     'context_inputs': [observed('stripe_geometry', 'structured record', 'Map marking and crossing geometry with source identity.')],
                     'sweep_dimensions': [observed('oncoming_gap_setup', 'm', 'Physical initial spacing, with realized body gap measured separately.'),
                                          observed('following_gap_setup', 'm', 'Physical initial spacing, with realized body gap measured separately.')],
                     'landmarks': [], 'recording_needs': needs,
                     'limitations': ['No legal safety or impediment cutoff is supplied.',
                                     'Statutory zone extent and other subsections require separate source verification.']}}
        observable_refs.append(write('judgment-' + ('impediment' if impediment else 'safety') + '.json', entry))
    refs['judgment_observables'] = observable_refs
    variables = [
        {'name': 'turn_signal_command', 'kind': 'controller', 'range_or_domain': 'on or off', 'used_by_laws': [LAW_ID]},
        {'name': 'commanded_turn_path', 'kind': 'controller', 'range_or_domain': 'left turn across marking', 'used_by_laws': [LAW_ID]},
        {'name': 'oncoming_gap_setup', 'kind': 'world_setup', 'range_or_domain': 'initial distance in m', 'used_by_laws': [LAW_ID]},
        {'name': 'following_gap_setup', 'kind': 'world_setup', 'range_or_domain': 'initial distance in m', 'used_by_laws': [LAW_ID]},
    ]
    binding = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft', 'established_contexts': ['intersection', 'left turn', 'pavement striping'],
               'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}], 'context_refs': [],
               'fixed_parameters': [], 'variable_parameters': variables}
    refs['bindings'] = write('bindings.json', binding)
    recording = {'channels': [channel('ego_body_history', 'Native ego transform and body envelope per simulator frame'),
                              channel('signal_history', 'Native ego left-signal control state per simulator frame'),
                              channel('oncoming_history', 'Native oncoming transform and body envelope per simulator frame'),
                              channel('following_history', 'Native following transform and body envelope per simulator frame')],
                 'context_inputs': [context('stripe_geometry', 'Native map lane marking, crossing geometry and verified source context')],
                 'limitations': ['Actual zone extent and statutory subsections remain unverified until source-backed Native capture.',
                                 'No legal safety or impediment judgment is inferred from physical gaps.']}
    assignments_on = {'turn_signal_command': {'kind': 'controller', 'value': True, 'note': 'Command left signal before stripe'},
                      'commanded_turn_path': {'kind': 'controller', 'value': 'left_turn_crossing', 'note': 'Same turn path in both probes'},
                      'oncoming_gap_setup': {'kind': 'world_setup', 'value': 40.0, 'unit': 'm', 'note': 'Initial placement only'},
                      'following_gap_setup': {'kind': 'world_setup', 'value': 20.0, 'unit': 'm', 'note': 'Initial placement only'}}
    cases = []
    cases.append({'case_id': ROOT.name + '__baseline', 'target_law_id': None, 'target_type': 'baseline',
                  'rationale': 'Shared physical crossing baseline; legal predicates unresolved.',
                  'variable_assignments': assignments_on, 'recording_description': recording,
                  'unresolved_judgment_calls': [j['phrase'] for j in judgments]})
    for label, signaled in [('signaled', True), ('unsignaled', False)]:
        import copy
        assignment = copy.deepcopy(assignments_on)
        assignment['turn_signal_command']['value'] = signaled
        assignment['turn_signal_command']['note'] = 'Command left signal before stripe' if signaled else 'Do not command left signal'
        cases.append({'case_id': ROOT.name + '__' + label + '_left_turn', 'target_law_id': LAW_ID,
                      'target_type': 'boundary_probe', 'rationale': 'Paired signal command comparison with the same authored traffic setup.',
                      'variable_assignments': assignment, 'recording_description': recording,
                      'unresolved_judgment_calls': [j['phrase'] for j in judgments],
                      'paired_probe_id': ROOT.name + '__signal_pair',
                      'deliberate_differences': ['turn_signal_command'],
                      'probe': {'primary_variable': 'turn_signal_command',
                                'comparison_or_standard': 'Prior appropriate turn signal requirement; realized control state measured.',
                                'target_value_or_branch': signaled}})
    sweeps = []
    for judgment in judgments:
        sweeps.append({'sweep_id': 'c109755-' + ('impediment' if 'impediment' in judgment['phrase'] else 'safety'),
                       'target_law_id': LAW_ID, 'judgment_refs': [judgment], 'status': 'incomplete',
                       'rationale': 'Physical coverage sweep awaits source-backed zone extent and feasible Native traffic ranges.',
                       'missing_inputs': ['Verified statutory zone extent and subsection 3/4 applicability',
                                          'Feasible Native spacing range and capture-backed realization measurements']})
    refs['cases'] = write('cases.json', {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                                        'cases': cases, 'sweep_specs': sweeps,
                                        'sweeps_expanded': True})
    write('semantic-index.json', {'format': 'worker-semantic-delivery', 'assignment_id': ROOT.name, 'stages': refs})
    # Full description is shared exactly with both selected construction contracts.
    for relative in ('construction.json', 'cases/unsignaled/construction.json'):
        path = ROOT / relative
        value = json.loads(path.read_text())
        value['recording_description'] = recording
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
