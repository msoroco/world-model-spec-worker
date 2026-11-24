"""Build exact-source draft canonical stages for two selected CPU cases."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
LAW = 'NRS-484B-283-1d3'
TEMPLATE = LAW + '@pedestrian'


def write(name, value):
    path = HERE / 'proposals' / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': path.relative_to(HERE).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    quote = plan['source_law']['text']
    description = json.loads((HERE / 'draft-bundles/controlled_1/primary/construction.json').read_text())['recording_description']
    assert quote == json.loads((HERE.parents[1] / 'inputs' / HERE.name / 'assignment.json').read_text())['law']['text']
    relevance = {'cell_id': 'C10316', 'actor': 'pedestrian', 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': quote,
                                    'applies_to': ['pedestrian'],
                                    'relevance_type': 'specific_match', 'confidence': 'medium',
                                    'notes': 'Original governing pixels and exception applicability require later review.'}],
                 'borderline_excluded': []}
    judgments = [
        ('signals exhibiting the words “Walk,” “Don’t Walk,” “Wait” or similar symbols are in place',
         'An OpenDRIVE head and Native state readback do not establish original displayed icon or countdown.'),
        ('a pedestrian who entered the highway lawfully pursuant to subparagraph (1)',
         'Lawful prior entry depends on original pre-entry pixels and the cited Walk clause.'),
        ('other place of safety',
         'Original destination and its safety status need an independent judgment.'),
        ('Except as otherwise provided in NRS 484B.287',
         'The cross-referenced crossing exceptions require original context review.'),
        ('484B.290',
         'The cross-referenced blind-person condition requires original context review.'),
        ('484B.350',
         'The cross-referenced school-lane condition requires original context review.'),
    ]
    for phrase, _ in judgments:
        assert phrase in quote
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': 'pedestrian',
                'status': 'draft', 'quote': quote,
                'structure': {
                    'activation': {'description': 'A pedestrian faces a governing no-countdown flashing pedestrian signal.',
                                   'source_clause': 'flashing but is not accompanied by a countdown timer'},
                    'obligation': {'description': 'Measure first entry and continuation before steady indication.',
                                   'source_clause': 'a pedestrian may not proceed to cross the highway'},
                    'exceptions': [
                        {'source_clause': 'Except as otherwise provided in NRS 484B.287',
                         'description': 'Cited crossing exceptions require original context.'},
                        {'source_clause': '484B.290',
                         'description': 'Cited blind-person rule requires original context.'},
                        {'source_clause': '484B.350',
                         'description': 'Cited school-lane rule requires original context.'},
                        {'source_clause': 'a pedestrian who entered the highway lawfully pursuant to subparagraph (1)',
                         'description': 'Lawful Walk entry permits continuation with a safety deadline.'}],
                    'timing': {'description': 'Separate first entry from prior Walk entry and full-body safety arrival.',
                               'source_clause': 'before the “Don’t Walk” or “Wait” indication or an upraised hand symbol is illuminated and steady'},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note}
                                              for phrase, note in judgments]},
                'parameter_refs': []}
    observable_names = ('native_display_program', 'native_display_program',
                        'rel.occupies', 'rel.occupies', 'native_display_program',
                        'native_display_program')
    units = {channel['name']: channel['unit'] for channel in description['channels']}
    observed = []
    for index, ((phrase, note), name) in enumerate(zip(judgments, observable_names)):
        item = {'name': name, 'unit': units[name],
                'description': 'Retain original source observations for independent statutory-context review.'}
        context = {'name': 'introductory_exceptions', 'unit': 'structured',
                   'description': 'Retain cited-law exception context without deciding applicability.'}
        value = {'template_id': TEMPLATE, 'phrase': phrase, 'note': note,
                 'status': 'draft', 'observable_requirements': {
                     'observables': [item], 'context_inputs': [context],
                     'sweep_dimensions': [], 'landmarks': [],
                     'recording_needs': [item],
                     'limitations': [note, 'Synthetic rows do not settle original pixels or legal applicability.']}}
        observed.append(write(f'judgment_observables_{index}.json', value))
    binding = {'cell_id': 'C10316', 'actor': 'pedestrian', 'status': 'draft',
               'established_contexts': [], 'law_refs': [{'template_id': TEMPLATE,
                                                         'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [
                   {'name': 'requested_flash_start_s', 'kind': 'world_setup',
                    'range_or_domain': '0.5 or 2.0 seconds as engineering scenario settings',
                    'used_by_laws': [LAW]},
                   {'name': 'actual_entry_state', 'kind': 'subject_behavior',
                    'range_or_domain': 'source-observed Walk or flashing indication at first body entry',
                    'used_by_laws': [LAW]}]}
    ids = [item['case_id'] for item in plan['cases']]
    common = {'actual_entry_state': {'kind': 'subject_behavior', 'value': None}}
    baseline = {'case_id': HERE.name + '__baseline', 'target_law_id': None,
                'target_type': 'baseline', 'rationale': 'Unselected common crossing context.',
                'variable_assignments': {**common, 'requested_flash_start_s':
                                         {'kind': 'world_setup', 'value': None}},
                'recording_description': description,
                'unresolved_judgment_calls': [phrase for phrase, _ in judgments]}
    cases = [baseline]
    for case_id, value in zip(ids, (2.0, .5)):
        cases.append({'case_id': case_id, 'target_law_id': LAW,
                      'target_type': 'judgment_sweep',
                      'rationale': 'Compare original first highway entry while requested indication is Walk or no-countdown flashing; keep legal judgment open.',
                      'paired_probe_id': 'c10316-no-countdown-entry-pair',
                      'deliberate_differences': ['requested_flash_start_s'],
                      'probe': {'primary_variable': 'requested_flash_start_s',
                                'comparison_or_standard': 'original entry state under exact clause',
                                'target_value_or_branch': value},
                      'variable_assignments': {**common, 'requested_flash_start_s':
                                               {'kind': 'world_setup', 'value': value}},
                      'recording_description': description,
                      'unresolved_judgment_calls': [phrase for phrase, _ in judgments]})
    proposal = {'cell_id': 'C10316', 'actor': 'pedestrian', 'status': 'draft',
                'cases': cases, 'sweeps_expanded': True,
                'sweep_specs': [{'sweep_id': 'c10316-original-signal-and-exception-review',
                                 'target_law_id': LAW, 'status': 'incomplete',
                                 'judgment_refs': [{'phrase': phrase, 'note': note}
                                                   for phrase, note in judgments],
                                 'rationale': 'Two source-shaped entry-state probes are prepared; actual governing display and cited-law applicability require original local review.',
                                 'missing_inputs': ['Original Native pedestrian-head pixels and governance',
                                                    'Independent countdown and exception-context review']}]}
    stages = {'relevance_batch': write('relevance_batch.json', relevance),
              'relevance': write('relevance.json', relevance),
              'template': write('template.json', template),
              'judgment_observables': observed,
              'bindings': write('bindings.json', binding),
              'cases': write('cases.json', proposal)}
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': HERE.name, 'stages': stages})
    print(json.dumps({'selected_cases': ids, 'judgment_observables': len(observed)}))


if __name__ == '__main__':
    main()
