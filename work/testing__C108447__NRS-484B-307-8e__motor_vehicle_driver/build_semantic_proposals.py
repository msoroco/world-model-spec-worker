"""Build source-hashed draft semantic stages for the exact property-bypass cases.

These stages preserve observation and intent as unresolved source questions.
They do not assert parcel authority, physical realization, or a legal verdict.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
PREFIX = FOLDER.name
LAW = 'NRS-484B-307-8e'
ACTOR = 'motor_vehicle_driver'
CELL = 'C108447'
SUFFIXES = ('private_bypass', 'public_bypass', 'ordinary_crossing',
            'no_approach_red', 'destination_red', 'other_purpose')
VARIABLES = ('parcel_class', 'route_class', 'approach_state',
             'destination_state', 'avoidance_purpose')
KINDS = {'parcel_class': 'world_setup', 'route_class': 'controller',
         'approach_state': 'world_setup', 'destination_state': 'world_setup',
         'avoidance_purpose': 'world_setup'}
UNITS = {'parcel_class': 'categorical source class',
         'route_class': 'categorical route request',
         'approach_state': 'categorical signal request',
         'destination_state': 'categorical signal request',
         'avoidance_purpose': 'categorical sourced purpose'}
VALUES = {
    'private_bypass': ('private', 'property', 'red_alone', 'green', 'avoid_red'),
    'public_bypass': ('public', 'property', 'red_alone', 'green', 'avoid_red'),
    'ordinary_crossing': ('private', 'roadway', 'red_alone', 'green', 'avoid_red'),
    'no_approach_red': ('private', 'property', 'green', 'green', 'avoid_red'),
    'destination_red': ('private', 'property', 'red_alone', 'red_alone', 'avoid_red'),
    'other_purpose': ('private', 'property', 'red_alone', 'green', 'other'),
}
CHANGED = {'private_bypass': 'parcel_class', 'public_bypass': 'parcel_class',
           'ordinary_crossing': 'route_class', 'no_approach_red': 'approach_state',
           'destination_red': 'destination_state', 'other_purpose': 'avoidance_purpose'}
PHRASE = 'to avoid the red signal'
NOTE = 'Avoidance purpose is separately sourced; route shape alone does not establish intent.'


def write(name: str, value: dict) -> dict:
    path = FOLDER / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    return {'path': str(path.relative_to(FOLDER)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build() -> dict:
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    quote = plan['law_text']
    if (plan['law_id'], plan['cell_id'], plan['actor']) != (LAW, CELL, ACTOR):
        raise ValueError('exact assignment identity changed')
    if [item['case_id'] for item in plan['cases']] != [PREFIX + '__' + s for s in SUFFIXES]:
        raise ValueError('six selected cases changed')
    relevance = {'status': 'draft', 'cell_id': CELL, 'actor': ACTOR,
                 'relevant_laws': [{'law_id': LAW, 'quote': quote,
                                    'applies_to': [ACTOR], 'confidence': 'high'}],
                 'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance-batch.json', relevance),
            'relevance': write('relevance.json', relevance)}
    template_id = LAW + '@' + ACTOR
    template = {'status': 'draft', 'law_id': LAW, 'actor': ACTOR,
                'template_id': template_id, 'quote': quote,
                'structure': {'activation': {'source_clause': 'Where the signal is a steady red signal alone'},
                              'obligation': {'source_clause': 'Vehicular traffic facing the signal may not proceed on or through any private or public property to enter the intersecting street where traffic is not facing a red signal to avoid the red signal.'},
                              'exceptions': [], 'timing': {'source_clause': 'to enter the intersecting street'},
                              'judgment_calls_needed': [{'phrase': PHRASE, 'note': NOTE}]},
                'parameter_refs': [{'name': name, 'unit': UNITS[name]} for name in VARIABLES]}
    refs['template'] = write('template.json', template)
    needs = [
        ('source parcel classification and boundaries', 'source observation', 'Reviewed original parcel and road boundary source'),
        ('ego body path and street entry', 'source observation', 'Original body path and intersecting street entry'),
        ('approach signal identity, facing and state', 'source observation', 'Original signal identity, orientation and state'),
        ('destination street traffic signal', 'source observation', 'Original destination signal context'),
        ('separate avoidance purpose', 'source observation', 'Separately authored purpose source, independent of route shape'),
    ]
    observed = {'status': 'draft', 'template_id': template_id,
                'phrase': PHRASE, 'note': NOTE,
                'observable_requirements': {
                    'observables': [{'name': n, 'unit': u, 'description': d} for n, u, d in needs],
                    'context_inputs': [{'name': 'reviewed original map and parcel authority',
                                        'unit': 'source record',
                                        'description': 'Retained OpenDRIVE and independent parcel status source'}],
                    'sweep_dimensions': [{'name': 'avoidance_purpose',
                                          'unit': UNITS['avoidance_purpose'],
                                          'description': 'Source-authored purpose variation; original motion checked separately'}],
                    'landmarks': [],
                    'recording_needs': [{'name': n, 'unit': u, 'description': d} for n, u, d in needs],
                    'limitations': ['Intent cannot be inferred from route geometry.',
                                    'Physical parcel status and signal state require original source review.']}}
    refs['judgment_observables'] = [write('judgment-observables.json', observed)]
    binding = {'status': 'draft', 'cell_id': CELL, 'actor': ACTOR,
               'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{'name': name, 'kind': KINDS[name],
                                        'range_or_domain': ', '.join(sorted({VALUES[s][i] for s in SUFFIXES})),
                                        'used_by_laws': [LAW]}
                                       for i, name in enumerate(VARIABLES)]}
    refs['bindings'] = write('bindings.json', binding)
    description = json.loads((FOLDER / 'constructions/private_bypass.json').read_text())['recording_description']
    cases = []
    for suffix in ('baseline_reference',) + SUFFIXES:
        selected = suffix if suffix != 'baseline_reference' else 'private_bypass'
        source_description = json.loads((FOLDER / 'constructions' / (selected + '.json')).read_text())['recording_description']
        if source_description != description:
            raise ValueError('case recording descriptions differ')
        assignments = {name: {'kind': KINDS[name], 'value': VALUES[selected][i],
                              'unit': UNITS[name]}
                       for i, name in enumerate(VARIABLES)}
        case = {'case_id': PREFIX + '__' + suffix, 'target_law_id': LAW,
                'target_type': 'baseline' if suffix == 'baseline_reference' else 'judgment_sweep',
                'rationale': 'Shared source-observation reference' if suffix == 'baseline_reference'
                else 'Exact physical contrast; original observation and purpose remain unresolved',
                'variable_assignments': assignments,
                'recording_description': source_description,
                'unresolved_judgment_calls': [{'phrase': PHRASE, 'note': NOTE}]}
        if suffix != 'baseline_reference':
            variable = CHANGED[suffix]
            case.update({'paired_probe_id': 'property_bypass_' + variable,
                         'deliberate_differences': [variable],
                         'probe': {'primary_variable': variable,
                                   'comparison_or_standard': 'Original source clause and measured physical attempt; no legal verdict',
                                   'target_value_or_branch': VALUES[selected][VARIABLES.index(variable)]}})
        cases.append(case)
    cases_stage = {'status': 'draft', 'cell_id': CELL, 'actor': ACTOR,
                   'cases': cases,
                   'sweep_specs': [{'sweep_id': 'avoidance_purpose_pending_original_source',
                                   'target_law_id': LAW,
                                   'judgment_refs': [{'phrase': PHRASE, 'note': NOTE}],
                                   'status': 'incomplete',
                                   'rationale': 'Original source-bound purpose and physical feasibility are required before freezing a sweep.',
                                   'missing_inputs': ['Reviewed original map and parcel authority',
                                                      'Original feasible purpose variation and Native motion']}],
                   'sweeps_expanded': True}
    refs['cases'] = write('cases.json', cases_stage)
    index = {'format': 'worker-semantic-delivery', 'assignment_id': PREFIX,
             'stages': refs}
    write('semantic-index.json', index)
    return {'stage_count': 6, 'selected_cases': len(SUFFIXES),
            'physical_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
