"""Build canonical draft stages for the four exact steady indication cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = 'NRS-484B-283-1d4'
TEMPLATE = LAW + '@pedestrian'


def write(name, value):
    path = HERE / 'proposals' / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': path.relative_to(HERE).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    quote = assignment['law']['text']
    if plan['source_law']['text'] != quote:
        raise ValueError('Selected law text differs from frozen input')
    construction = json.loads((HERE / 'execution-manifest.json').read_text())['cases'][0]['construction']
    description = json.loads((HERE / construction).read_text())['recording_description']
    relevance = {'cell_id': 'C10316', 'actor': 'pedestrian', 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': quote,
                                    'applies_to': ['pedestrian'],
                                    'relevance_type': 'specific_match', 'confidence': 'medium',
                                    'notes': 'Original governing signal and exceptions require local source review.'}],
                 'borderline_excluded': []}
    judgments = [
        ('signals exhibiting the words “Walk,” “Don’t Walk,” “Wait” or similar symbols are in place',
         'Original pixels and direction must identify a governing pedestrian signal.'),
        ('entered the highway lawfully pursuant to subparagraph (1) or (2)',
         'Prior lawful entry depends on original Walk or countdown source and cited clauses.'),
        ('other place of safety',
         'Original destination and its safety status need independent review.'),
        ('as soon as possible',
         'The declared progress surrogate is engineering evidence, not a legal cutoff.'),
        ('Except as otherwise provided in NRS 484B.287',
         'Cited crossing exceptions need original context.'),
        ('484B.290', 'Blind pedestrian applicability needs original context.'),
        ('484B.350', 'School crossing guard applicability needs original context.'),
    ]
    if any(phrase not in quote for phrase, _ in judgments):
        raise ValueError('Judgment phrase absent from exact law')
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': 'pedestrian',
                'status': 'draft', 'quote': quote,
                'structure': {
                    'activation': {'description': 'Pedestrian faces a governing steady Don’t Walk or Wait indication.',
                                   'source_clause': 'While the “Don’t Walk” or “Wait” indication or an upraised hand symbol is illuminated and steady'},
                    'obligation': {'description': 'Measure first entry, lawful prior entry and progress to safety.',
                                   'source_clause': 'a pedestrian may not proceed to cross the highway'},
                    'exceptions': [
                        {'source_clause': 'Except as otherwise provided in NRS 484B.287',
                         'description': 'Cited crossing exceptions need original context.'},
                        {'source_clause': '484B.290', 'description': 'Cited blind pedestrian condition needs original context.'},
                        {'source_clause': '484B.350', 'description': 'Cited guard condition needs original context.'},
                        {'source_clause': 'entered the highway lawfully pursuant to subparagraph (1) or (2)',
                         'description': 'Prior lawful Walk or countdown entry may permit continuation.'}],
                    'timing': {'description': 'Separate first entry from steady illumination and continuation to safety.',
                               'source_clause': 'as soon as possible'},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note}
                                              for phrase, note in judgments]},
                'parameter_refs': []}
    names = ('native_display_program', 'native_display_program', 'rel.occupies',
             'kin.position', 'rel.occupies', 'native_display_program', 'native_display_program')
    units = {channel['name']: channel['unit'] for channel in description['channels']}
    observed = []
    for index, ((phrase, note), name) in enumerate(zip(judgments, names)):
        item = {'name': name, 'unit': units[name],
                'description': 'Retain original source observations for independent statutory review.'}
        context = {'name': 'introductory_exceptions', 'unit': 'structured',
                   'description': 'Retain cited-law context without deciding applicability.'}
        observed.append(write(f'judgment_observables_{index}.json', {
            'template_id': TEMPLATE, 'phrase': phrase, 'note': note, 'status': 'draft',
            'observable_requirements': {'observables': [item], 'context_inputs': [context],
                                        'sweep_dimensions': [], 'landmarks': [],
                                        'recording_needs': [item],
                                        'limitations': [note, 'Synthetic rows do not establish physical or legal facts.']}}))
    binding = {'cell_id': 'C10316', 'actor': 'pedestrian', 'status': 'draft',
               'established_contexts': [],
               'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [
                   {'name': 'requested_steady_start_s', 'kind': 'world_setup',
                    'range_or_domain': '0.5 or 4.0 seconds as engineering settings', 'used_by_laws': [LAW]},
                   {'name': 'requested_prior_entry_state', 'kind': 'world_setup',
                    'range_or_domain': 'Walk or flashing countdown as engineering settings', 'used_by_laws': [LAW]},
                   {'name': 'actual_entry_state', 'kind': 'subject_behavior',
                    'range_or_domain': 'source observed Walk, countdown or steady at first body entry',
                    'used_by_laws': [LAW]}]}
    common = {'actual_entry_state': {'kind': 'subject_behavior', 'value': None}}
    baseline = {'case_id': HERE.name + '__baseline', 'target_law_id': None,
                'target_type': 'baseline', 'rationale': 'Unselected common crossing context.',
                'variable_assignments': {**common,
                                         'requested_steady_start_s': {'kind': 'world_setup', 'value': None},
                                         'requested_prior_entry_state': {'kind': 'world_setup', 'value': None}},
                'recording_description': description,
                'unresolved_judgment_calls': [phrase for phrase, _ in judgments]}
    values = [(4.0, 'Walk'), (.5, 'steady'), (4.0, 'flashing_countdown'), (4.0, 'Walk')]
    cases = [baseline]
    for source, (steady, prior) in zip(plan['cases'], values):
        selected = next(entry for entry in json.loads((HERE / 'execution-manifest.json').read_text())['cases']
                        if entry['case_id'] == source['case_id'])
        case_description = json.loads((HERE / selected['construction']).read_text())['recording_description']
        cases.append({'case_id': source['case_id'], 'target_law_id': LAW,
                      'target_type': 'judgment_sweep',
                      'rationale': 'Preserve exact requested entry timing or prior entry branch while original signal and legal applicability remain open.',
                      'paired_probe_id': 'c10316-d4-steady-and-prior-entry',
                      'deliberate_differences': ['requested_steady_start_s', 'requested_prior_entry_state'],
                      'probe': {'primary_variable': 'requested_steady_start_s' if 'witness' in source['case_id'] else 'requested_prior_entry_state',
                                'comparison_or_standard': 'original entry state and progress under exact clause',
                                'target_value_or_branch': steady if 'witness' in source['case_id'] else prior},
                      'variable_assignments': {**common,
                                               'requested_steady_start_s': {'kind': 'world_setup', 'value': steady},
                                               'requested_prior_entry_state': {'kind': 'world_setup', 'value': prior}},
                      'recording_description': case_description,
                      'unresolved_judgment_calls': [phrase for phrase, _ in judgments]})
    proposal = {'cell_id': 'C10316', 'actor': 'pedestrian', 'status': 'draft',
                'cases': cases, 'sweeps_expanded': True,
                'sweep_specs': [{'sweep_id': 'c10316-d4-original-signal-and-exception-review',
                                 'target_law_id': LAW, 'status': 'incomplete',
                                 'judgment_refs': [{'phrase': phrase, 'note': note}
                                                   for phrase, note in judgments],
                                 'rationale': 'Four exact source shaped probes are prepared; original governing signal and cited-law applicability require local review.',
                                 'missing_inputs': ['Original signal pixels and governance',
                                                    'Independent exception and legal judgment review']}]}
    stages = {'relevance_batch': write('relevance_batch.json', relevance),
              'relevance': write('relevance.json', relevance),
              'template': write('template.json', template),
              'judgment_observables': observed,
              'bindings': write('bindings.json', binding),
              'cases': write('cases.json', proposal)}
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': HERE.name, 'stages': stages})
    print(json.dumps({'selected_cases': len(cases) - 1,
                      'judgment_observables': len(observed)}))


if __name__ == '__main__':
    main()
