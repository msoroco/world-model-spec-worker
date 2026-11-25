"""Build draft canonical semantic stages from exact frozen law and selected cases."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
NATIVE = ROOT / 'native'
OUT = ROOT / 'proposals'
ASSIGNMENT = ROOT.name
LAW_ID = 'NRS-484B-210-1'
ACTOR = 'motor_vehicle_driver'
TEMPLATE = LAW_ID + '@' + ACTOR


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    return {'path': 'proposals/' + name, 'sha256': sha(path)}


def main():
    frozen = json.loads((REPO / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())
    law = frozen['law']
    assert law['id'] == LAW_ID and frozen['cell']['layout'] == 'one_way_multilane'
    quote = law['text']
    relevance = {'cell_id': 'C146314', 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW_ID, 'quote': quote,
                                    'applies_to': [ACTOR],
                                    'relevance_type': 'specific_match',
                                    'confidence': 'high',
                                    'notes': 'Frozen overtaking-right cell; paragraph (b) remains unbound.'}],
                 'borderline_excluded': []}
    relevance_ref = write('relevance.json', relevance)
    relevance_batch_ref = write('relevance_batch.json', relevance)
    assert relevance_ref['sha256'] == relevance_batch_ref['sha256']
    snippets = [
        'When the driver of the vehicle overtaken is making or signaling to make a left turn.',
        'Upon a highway with unobstructed pavement which is not occupied by parked vehicles and which is of sufficient width for two or more lines of moving vehicles in each direction.',
        'Upon a highway with unobstructed pavement which is not marked as a traffic lane and which is not occupied by parked vehicles',
        'Upon any highway on which traffic is restricted to one direction of movement, where the highway is free from obstructions and of sufficient width for two or more lines of moving vehicles.',
        'The provisions of subparagraph (1) of paragraph (c) of subsection 1 do not apply to:',
    ]
    assert all(text in quote for text in snippets)
    template = {'template_id': TEMPLATE, 'law_id': LAW_ID, 'actor': ACTOR,
                'status': 'draft', 'quote': quote,
                'structure': {
                    'activation': {'source_clause': 'The driver of a vehicle may overtake and pass upon the right of another vehicle',
                                   'description': 'Review original ego/lead body order, side and pass; authored targets do not establish activation.'},
                    'obligation': {'source_clause': 'only under the following conditions:',
                                   'description': 'At least one exact source alternative must hold; keep pavement, vehicle category and right-pass facts separate from requested construction.',
                                   'c1_excursion_limit': {'variable': 'unmarked_pavement_excursion',
                                                          'operator': '<=', 'value': 200, 'unit': 'ft',
                                                          'source_clause': 'does not travel more than 200 feet in the section of pavement not marked as a traffic lane'}},
                    'exceptions': [{'source_clause': text,
                                    'description': 'Exact-law alternative or subsection (4) category; original facts require independent source review.'}
                                   for text in snippets],
                    'timing': {'source_clause': 'While being driven in the section of pavement not marked as a traffic lane',
                               'description': 'Retain entry, interval and return; do not infer continuous condition from one frame.'},
                    'judgment_calls_needed': []},
                'parameter_refs': []}
    template_ref = write('template.json', template)
    fixed = [{'name': 'frozen_cell', 'kind': 'world_setup',
              'value': 'C146314 one_way_multilane/overtake_right/other_vehicle',
              'used_by_laws': [LAW_ID]}]
    variables = [
        ('requested_right_lane_obstruction', 'world_setup', 'false, true or not exercised'),
        ('requested_lead_left_signal', 'world_setup', 'false, true or not exercised'),
        ('requested_qualifying_category', 'world_setup', 'tow_car, ordinary_vehicle or not exercised'),
        ('requested_excursion_m', 'controller', '60.86, 60.96, 61.06 m or not exercised'),
        ('commanded_right_pass', 'controller', 'true for selected attempts'),
        ('observed_right_pass', 'subject_behavior', 'original source result pending'),
        ('observed_one_way_designation', 'subject_behavior', 'independent source review pending'),
        ('observed_lead_left_blinker', 'subject_behavior', 'original source result pending'),
        ('observed_excursion_m', 'subject_behavior', 'original source result pending'),
        ('observed_qualifying_category', 'subject_behavior', 'independent source review pending'),
    ]
    binding = {'cell_id': 'C146314', 'actor': ACTOR, 'status': 'draft',
               'established_contexts': [],
               'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': fixed,
               'variable_parameters': [{'name': name, 'kind': kind,
                                        'range_or_domain': domain,
                                        'used_by_laws': [LAW_ID]}
                                       for name, kind, domain in variables]}
    binding_ref = write('bindings.json', binding)
    old = json.loads((OUT / 'cases.json').read_text())
    by_suffix = {case['case_id'].split('__')[-1]: case for case in old['cases']}
    groups = {
        'witness': ('selected-paragraph-d', ['witness_1', 'witness_2'],
                    'requested_right_lane_obstruction', [False, True]),
        'exception_1': ('exception-1', ['exception_1_1', 'exception_1_2'],
                        'requested_lead_left_signal', [False, True]),
        'exception_3': ('current-c1', ['exception_3_1', 'exception_3_2'],
                        'requested_excursion_m', [61.06, 60.96]),
        'exception_4': ('exception-4', ['exception_4_1', 'exception_4_2'],
                        'requested_right_lane_obstruction', [False, True]),
        'exception_5': ('subsection-4', ['exception_5_1', 'exception_5_2'],
                        'requested_qualifying_category', ['tow_car', 'ordinary_vehicle']),
        'numeric_1': ('numeric-boundary', ['numeric_1_0', 'numeric_1_1', 'numeric_1_2'],
                      'requested_excursion_m', [60.86, 60.96, 61.06]),
    }
    kinds = {name: kind for name, kind, _ in variables}
    cases = []
    baseline = by_suffix['baseline'].copy()
    baseline['variable_assignments'] = {
        name: {'kind': kind, 'value': (True if name == 'commanded_right_pass' else None),
               'unit': ('m' if name in ('requested_excursion_m', 'observed_excursion_m') else 'categorical')}
        for name, kind in kinds.items()}
    cases.append(baseline)
    for group_name, (folder, suffixes, variable, values) in groups.items():
        for suffix, value in zip(suffixes, values):
            original = by_suffix[suffix]
            construction = json.loads((NATIVE / folder / suffix / 'primary/construction.json').read_text())
            assert construction['case_id'] == original['case_id']
            row = original.copy()
            row['target_type'] = 'boundary_probe'
            row['paired_probe_id'] = ASSIGNMENT + '__' + group_name + '_semantic_pair'
            row['deliberate_differences'] = [variable]
            row['probe'] = {'primary_variable': variable,
                            'comparison_or_standard': 'Exact source branch with original-source review pending',
                            'target_value_or_branch': {variable: value}}
            row['variable_assignments'] = json.loads(json.dumps(baseline['variable_assignments']))
            row['variable_assignments'][variable]['value'] = value
            row['recording_description'] = construction['recording_description']
            row['rationale'] = original.get('rationale', '') + ' Requested condition only; original physical and legal facts unverified.'
            if group_name == 'numeric_1':
                row['probe'].update({'threshold_ref': 'obligation.c1_excursion_limit',
                                     'operator': '<=', 'unit': 'ft',
                                     'test_value': value / 0.3048})
                row['epsilon_used'] = {'value': 0.1 / 0.3048, 'unit': 'ft',
                                       'description': 'Engineering neighboring measurement request'}
            cases.append(row)
    proposal = {'cell_id': 'C146314', 'actor': ACTOR, 'status': 'draft',
                'sweep_specs': [], 'sweeps_expanded': True, 'cases': cases}
    cases_ref = write('cases.json', proposal)
    index = {'format': 'worker-semantic-delivery', 'assignment_id': ASSIGNMENT,
             'stages': {'relevance_batch': relevance_batch_ref,
                        'relevance': relevance_ref, 'template': template_ref,
                        'judgment_observables': [], 'bindings': binding_ref,
                        'cases': cases_ref}}
    write('semantic-index.json', index)
    print('BUILT exact-law semantic draft stages for', len(cases) - 1, 'selected cases')


if __name__ == '__main__':
    main()
