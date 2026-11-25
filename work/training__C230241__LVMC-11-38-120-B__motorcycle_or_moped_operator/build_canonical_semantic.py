"""Build exact-law canonical stage proposals with original-source review pending."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = 'LVMC-11-38-120-B'
TEMPLATE = LAW + '@motorcycle_or_moped_operator'


def write(name, value):
    path = HERE / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': path.relative_to(HERE).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    quote = assignment['law']['text']
    if quote != plan['source_law_text']:
        raise ValueError('Law source differs from case plan')
    description = json.loads((HERE / 'construction.json').read_text())['recording_description']
    relevance = {'cell_id': 'C230241', 'actor': 'motorcycle_or_moped_operator',
                 'status': 'draft', 'relevant_laws': [{
                     'law_id': LAW, 'quote': quote,
                     'applies_to': ['motorcycle_or_moped_operator'],
                     'relevance_type': 'specific_match', 'confidence': 'medium',
                     'notes': 'Covered vehicle class, original lamp reach, discernibility and civil time require local review.'}],
                 'borderline_excluded': []}
    judgments = [
        ('vehicles covered under this Section, as provided in Section 11.38.080',
         'Vehicle coverage under referenced Section 11.38.080 requires legal and original identity review.',
         'vehicle_covered'),
        ('white light visible at least three hundred feet',
         'Original forward headlamp colour and calibrated 300-foot reach require camera and site review.',
         'front_visible_ft'),
        ('red light plainly visible from at least five hundred feet to the rear',
         'Original rear lamp colour, mounting and calibrated 500-foot visibility require review.',
         'rear_visible_ft'),
        ('one-half hour after sunset to one-half hour before sunrise',
         'Original site/date civil clock and continuous motion frame join require review.',
         'utc_s'),
        ('not clearly discernible at a distance of at least five hundred feet ahead',
         'Original visibility and unfavorable atmosphere need independent 500-foot discernibility review.',
         'discernible_500ft'),
    ]
    if any(phrase not in quote for phrase, _, _ in judgments):
        raise ValueError('Judgment clause differs from exact statute')
    template = {'template_id': TEMPLATE, 'law_id': LAW,
                'actor': 'motorcycle_or_moped_operator', 'status': 'draft',
                'quote': quote, 'structure': {
                    'activation': {'description': 'Covered vehicle in motion within the statutory night or low-visibility period.',
                                   'source_clause': judgments[0][0]},
                    'obligation': {'description': 'At least one white forward headlamp and one red rear mounted tail lamp, each with its stated visibility and burning conditions.',
                                   'source_clause': judgments[1][0]},
                    'exceptions': [],
                    'timing': {'description': 'Continuous burning while moving in night or reduced 500-foot discernibility.',
                               'source_clause': judgments[3][0]},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note}
                                              for phrase, note, _ in judgments]},
                'parameter_refs': []}
    units = {channel['name']: channel['unit'] for channel in description['channels']}
    observed = []
    for index, (phrase, note, channel) in enumerate(judgments):
        item = {'name': channel, 'unit': units[channel],
                'description': note}
        result = {'template_id': TEMPLATE, 'phrase': phrase, 'note': note,
                  'status': 'draft', 'observable_requirements': {
                      'observables': [item], 'context_inputs': [],
                      'sweep_dimensions': [], 'landmarks': [],
                      'recording_needs': [item],
                      'limitations': [note, 'Synthetic lamp and range rows do not prove original physical visibility or legal compliance.']}}
        observed.append(write(f'judgment_observables_{index}.json', result))
    binding = {'cell_id': 'C230241', 'actor': 'motorcycle_or_moped_operator',
               'status': 'draft', 'established_contexts': [],
               'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{'name': 'requested_light_state',
                                        'kind': 'controller',
                                        'range_or_domain': 'LowBeam|Position or Position',
                                        'used_by_laws': [LAW]}]}
    ids = [item['case_id'] for item in plan['cases']]
    cases = [{'case_id': HERE.name + '__baseline', 'target_law_id': None,
              'target_type': 'baseline',
              'rationale': 'Unselected common motorcycle, site, vendor, weather and capture context.',
              'variable_assignments': {'requested_light_state':
                                       {'kind': 'controller', 'value': None}},
              'recording_description': description,
              'unresolved_judgment_calls': [phrase for phrase, _, _ in judgments]}]
    for case_id, light in zip(ids, ('LowBeam|Position', 'Position')):
        cases.append({'case_id': case_id, 'target_law_id': LAW,
                      'target_type': 'boundary_probe',
                      'rationale': 'Contrast requested forward lamp state while measuring independent original visibility, colour and timing sources.',
                      'paired_probe_id': 'c230241-headlamp-state-pair',
                      'deliberate_differences': ['requested_light_state'],
                      'probe': {'primary_variable': 'requested_light_state',
                                'comparison_or_standard': '300-foot original white forward lamp reach and 500-foot original red rear visibility',
                                'target_value_or_branch': light},
                      'variable_assignments': {'requested_light_state':
                                               {'kind': 'controller', 'value': light}},
                      'recording_description': description,
                      'unresolved_judgment_calls': [phrase for phrase, _, _ in judgments]})
    proposal = {'cell_id': 'C230241', 'actor': 'motorcycle_or_moped_operator',
                'status': 'draft', 'cases': cases, 'sweeps_expanded': True,
                'sweep_specs': [{'sweep_id': 'c230241-original-lamp-review',
                                 'target_law_id': LAW, 'status': 'incomplete',
                                 'judgment_refs': [{'phrase': phrase, 'note': note}
                                                   for phrase, note, _ in judgments],
                                 'rationale': 'Two software-prepared lamp-state cases await original calibrated source review.',
                                 'missing_inputs': ['Original Native lamp pixels and calibrated reach',
                                                    'Site/date clock and 500-foot discernibility review']}]}
    stages = {'relevance_batch': write('relevance_batch.json', relevance),
              'relevance': write('relevance.json', relevance),
              'template': write('template.json', template),
              'judgment_observables': observed,
              'bindings': write('bindings.json', binding),
              'cases': write('cases.json', proposal)}
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': HERE.name, 'stages': stages})
    print(json.dumps({'selected_cases': ids, 'judgments': len(observed)}))


if __name__ == '__main__':
    main()
