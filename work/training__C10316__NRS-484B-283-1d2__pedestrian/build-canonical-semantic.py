"""Build draft semantic stages for the exact flashing-countdown clause."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = 'NRS-484B-283-1d2'
TEMPLATE = LAW + '@pedestrian'


def write(name, value):
    path = HERE / 'proposals' / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': path.relative_to(HERE).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    quote = assignment['law']['text']
    assert quote == plan['source_law_text']
    description = json.loads((HERE / 'draft-bundles/probe_01/primary/construction.json').read_text())['recording_description']
    relevance = {'cell_id': 'C10316', 'actor': 'pedestrian', 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': quote,
                                    'applies_to': ['pedestrian'],
                                    'relevance_type': 'specific_match', 'confidence': 'medium',
                                    'notes': 'Original governing countdown pixels and exception applicability require local review.'}],
                 'borderline_excluded': []}
    judgments = [
        ('signals exhibiting the words “Walk,” “Don’t Walk,” “Wait” or similar symbols are in place',
         'The authored head and Native readback need original symbol and route-governance review.'),
        ('is flashing and is accompanied by a countdown timer',
         'Original synchronized indication and legible countdown digits must be reviewed.'),
        ('in the direction of the signal',
         'The source route and signal facing direction must be joined.'),
        ('complete the crossing before the countdown timer gets to zero',
         'Full body crossing completion and the original displayed-zero bracket must be measured.'),
        ('Except as otherwise provided in NRS 484B.287',
         'The crossing-location and diagonal exceptions require original context.'),
        ('484B.290',
         'The cited blind-person exception requires original context.'),
        ('484B.350',
         'The cited school-lane exception requires original context.'),
    ]
    assert all(phrase in quote for phrase, _ in judgments)
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': 'pedestrian',
                'status': 'draft', 'quote': quote,
                'structure': {
                    'activation': {'description': 'A governing illuminated flashing pedestrian indication is accompanied by a countdown timer.',
                                   'source_clause': 'is flashing and is accompanied by a countdown timer'},
                    'obligation': {'description': 'Measure full-body crossing completion before the displayed timer reaches zero.',
                                   'source_clause': 'must complete the crossing before the countdown timer gets to zero'},
                    'exceptions': [
                        {'source_clause': 'Except as otherwise provided in NRS 484B.287',
                         'description': 'Cited crossing exception requires original context.'},
                        {'source_clause': '484B.290',
                         'description': 'Cited blind-person exception requires original context.'},
                        {'source_clause': '484B.350',
                         'description': 'Cited school-lane exception requires original context.'}],
                    'timing': {'description': 'Compare original full-body highway clearance to original displayed-zero event.',
                               'source_clause': 'before the countdown timer gets to zero'},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note}
                                              for phrase, note in judgments]},
                'parameter_refs': []}
    names = ('native_display_program', 'display_camera_frame_join',
             'native_display_program', 'rel.occupies',
             'rel.occupies', 'rel.occupies', 'rel.occupies')
    units = {channel['name']: channel['unit'] for channel in description['channels']}
    observed = []
    for index, ((phrase, note), name) in enumerate(zip(judgments, names)):
        item = {'name': name, 'unit': units[name],
                'description': 'Retain source observations for independent statutory review.'}
        context = {'name': 'introductory_exceptions', 'unit': 'structured',
                   'description': 'Retain cited-law context without deciding applicability.'}
        value = {'template_id': TEMPLATE, 'phrase': phrase, 'note': note,
                 'status': 'draft', 'observable_requirements': {
                     'observables': [item], 'context_inputs': [context],
                     'sweep_dimensions': [], 'landmarks': [],
                     'recording_needs': [item],
                     'limitations': [note, 'Generated diagnostic rows do not establish original pixels or legal applicability.']}}
        observed.append(write(f'judgment_observables_{index}.json', value))
    binding = {'cell_id': 'C10316', 'actor': 'pedestrian', 'status': 'draft',
               'established_contexts': [],
               'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [
                   {'name': 'requested_displayed_zero_s', 'kind': 'world_setup',
                    'range_or_domain': '7 or 10 seconds as engineering scene settings',
                    'used_by_laws': [LAW]},
                   {'name': 'actual_clearance_time', 'kind': 'subject_behavior',
                    'range_or_domain': 'original full-body clearance time',
                    'used_by_laws': [LAW]}]}
    ids = [item['case_id'] for item in plan['cases']]
    assert len(ids) == 2
    common = {'actual_clearance_time': {'kind': 'subject_behavior', 'value': None}}
    baseline = {'case_id': HERE.name + '__baseline', 'target_law_id': None,
                'target_type': 'baseline', 'rationale': 'Unselected common crossing context.',
                'variable_assignments': {**common, 'requested_displayed_zero_s':
                                         {'kind': 'world_setup', 'value': None}},
                'recording_description': description,
                'unresolved_judgment_calls': [phrase for phrase, _ in judgments]}
    cases = [baseline]
    for case_id, value in zip(ids, (10, 7)):
        cases.append({'case_id': case_id, 'target_law_id': LAW,
                      'target_type': 'judgment_sweep',
                      'rationale': 'Compare full-body clearance against requested displayed zero while retaining original-display and statutory judgments.',
                      'paired_probe_id': 'c10316-countdown-clearance-pair',
                      'deliberate_differences': ['requested_displayed_zero_s'],
                      'probe': {'primary_variable': 'requested_displayed_zero_s',
                                'comparison_or_standard': 'original full-body clearance versus displayed zero',
                                'target_value_or_branch': value},
                      'variable_assignments': {**common, 'requested_displayed_zero_s':
                                               {'kind': 'world_setup', 'value': value}},
                      'recording_description': description,
                      'unresolved_judgment_calls': [phrase for phrase, _ in judgments]})
    proposal = {'cell_id': 'C10316', 'actor': 'pedestrian', 'status': 'draft',
                'cases': cases, 'sweeps_expanded': True,
                'sweep_specs': [{'sweep_id': 'c10316-original-countdown-and-exception-review',
                                 'target_law_id': LAW, 'status': 'incomplete',
                                 'judgment_refs': [{'phrase': phrase, 'note': note}
                                                   for phrase, note in judgments],
                                 'rationale': 'Two source-shaped deadline probes are prepared; actual display governance and cited-law applicability need original local review.',
                                 'missing_inputs': ['Original Native countdown pixels and governance',
                                                    'Independent exception-context review']}]}
    stages = {'relevance_batch': write('relevance_batch.json', relevance),
              'relevance': write('relevance.json', relevance),
              'template': write('template.json', template),
              'judgment_observables': observed,
              'bindings': write('bindings.json', binding),
              'cases': write('cases.json', proposal)}
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': HERE.name, 'stages': stages})
    print(json.dumps({'cases': ids, 'judgment_observables': len(observed)}))


if __name__ == '__main__':
    main()
