"""Build exact draft semantic stages from the frozen law and selected cases."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']
LAW_ID = ASSIGNMENT['law_id']
ACTOR = ASSIGNMENT['actor']
TEMPLATE_ID = LAW_ID + '@' + ACTOR
CASES = json.loads((HERE / 'proposals/cases.json').read_text())


def write(name, value):
    path = HERE / 'proposals' / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': sha256(path.read_bytes()).hexdigest()}


relevance = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR, 'status': 'draft',
             'relevant_laws': [{'law_id': LAW_ID, 'quote': LAW['text'],
                                'applies_to': [ACTOR], 'relevance_type': 'specific_match',
                                'confidence': 'high',
                                'notes': 'Frozen paved-road following cell fits the driver and following condition; actual lighting time and roadway occupancy require source review.'}],
             'borderline_excluded': []}
phrases = [('safe distance in advance of the vehicle',
            'Safe illumination distance has no numeric value in this assigned subsection.'),
           ('permissible under this chapter',
            'Native high/low beam bits do not independently establish a permissible distribution.')]
parameters = [
    ('headlamp_gap_ft', 'subject_behavior', 'measured nonnegative ground-body distance in ft'),
    ('requested_gap_ft', 'controller', 'requested 299, 300 or 301 ft boundary setup'),
    ('requested_uppermost_distribution', 'controller', 'requested beam-state setup'),
    ('lighting_time_premise', 'world_setup', 'separately sourced NRS 484D.100 time premise'),
    ('requested_roadway_position', 'world_setup', 'traveled portion or adjacent shoulder setup'),
]
template = {'template_id': TEMPLATE_ID, 'law_id': LAW_ID, 'actor': ACTOR,
            'status': 'draft', 'quote': LAW['text'],
            'structure': {'law_id': LAW_ID,
                          'activation': {'condition': 'Motor vehicle operated on the traveled highway or adjacent shoulder during NRS 484D.100 lighting times and following another vehicle to the rear.',
                                         'numeric_conditions': []},
                          'obligation': {'type': 'must',
                                         'description': 'Use a distribution permissible under the chapter other than the uppermost distribution while following within 300 ft; the opening clause also requires illumination to a safe distance.',
                                         'numeric_conditions': [{'variable': 'headlamp_gap_ft', 'operator': '<', 'value': 300, 'unit': 'ft'}]},
                          'exceptions': [],
                          'timing': {'description': 'Apply throughout the interval of following within 300 ft while the lighting-time and roadway premises hold.',
                                     'numeric_conditions': []},
                          'judgment_calls_needed': [{'phrase': p, 'note': n} for p, n in phrases]},
            'parameter_refs': [{'name': name, 'kind': kind, 'range_or_domain': domain}
                               for name, kind, domain in parameters]}
bindings = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR, 'status': 'draft',
            'established_contexts': ['paved_road', 'follow', 'other_vehicle'],
            'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
            'context_refs': [],
            'fixed_parameters': [{'name': 'cell_layout', 'value': 'paved_road',
                                  'rationale': 'Frozen C178038 catalog cell'}],
            'variable_parameters': [{'name': name, 'kind': kind,
                                     'range_or_domain': domain,
                                     'used_by_laws': [LAW_ID]}
                                    for name, kind, domain in parameters]}


def assignments(case):
    variables = case['variable_assignments']
    gap = variables['requested_gap_ft']['value']
    beam = variables['requested_uppermost_distribution']['value']
    lighting = variables['lighting_time_premise']['value']
    road = variables.get('requested_roadway_position', {}).get('value', 'driving')
    return {'headlamp_gap_ft': {'kind': 'subject_behavior', 'value': None},
            'requested_gap_ft': {'kind': 'controller', 'value': gap},
            'requested_uppermost_distribution': {'kind': 'controller', 'value': beam},
            'lighting_time_premise': {'kind': 'world_setup', 'value': lighting},
            'requested_roadway_position': {'kind': 'world_setup', 'value': road}}


selected = []
for prior in (item for item in CASES['cases'] if item.get('target_type') != 'baseline'):
    case = deepcopy(prior)
    suffix = case['case_id'].split('__')[-1]
    case['variable_assignments'] = assignments(case)
    case['target_type'] = 'boundary_probe'
    case['paired_probe_id'] = ('headlamp_300ft_boundary' if suffix in
                               ('night_299_upper', 'night_300_upper', 'night_301_upper')
                               else 'headlamp_' + suffix)
    case['deliberate_differences'] = ['requested_gap_ft'] if suffix in (
        'night_299_upper', 'night_300_upper', 'night_301_upper') else []
    case['probe'] = {'primary_variable': 'requested_gap_ft',
                     'comparison_or_standard': 'Measured 300 ft statutory boundary or controlled beam/time/roadway context; requested setup is not realized measurement.',
                     'target_value_or_branch': case['variable_assignments']['requested_gap_ft']['value']}
    if suffix in ('night_299_upper', 'night_300_upper', 'night_301_upper'):
        case['probe'].update(threshold_ref='obligation.numeric_conditions[0]',
                             test_value=case['variable_assignments']['requested_gap_ft']['value'],
                             operator='<', unit='ft')
        case['epsilon_used'] = {'value': 1, 'unit': 'ft',
                                'rationale': 'One-foot physical boundary sampling; not a legal tolerance.'}
    case['unresolved_judgment_calls'] = [p for p, _ in phrases]
    selected.append(case)
baseline = deepcopy(selected[0])
baseline.update(case_id=ASSIGNMENT['assignment_id'] + '__neutral_baseline',
                target_law_id=None, target_type='baseline',
                rationale='Neutral reference for selected comparison probes; no delivery recording')
for key in ('paired_probe_id', 'deliberate_differences', 'probe', 'epsilon_used'):
    baseline.pop(key, None)
semantic_cases = {'format': 'scenario-coverage-cases', 'status': 'draft',
                  'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR,
                  'sweeps_expanded': True,
                  'sweep_specs': [{'sweep_id': ASSIGNMENT['assignment_id'] + '__illumination_review',
                                   'target_law_id': LAW_ID,
                                   'judgment_refs': [{'phrase': p, 'note': n} for p, n in phrases],
                                   'status': 'incomplete',
                                   'missing_inputs': ['Original Native illumination pixels and independent civil-time/beam-permissibility sources are unavailable in CPU diagnostics.'],
                                   'rationale': 'Physical illumination/permissibility review remains source-dependent; do not invent a judgment threshold.'}],
                  'cases': [baseline, *selected]}


def observable(phrase, note):
    return {'template_id': TEMPLATE_ID, 'phrase': phrase, 'note': note,
            'status': 'draft', 'observable_requirements': {
                'observables': [{'name': 'headlamp_gap_ft', 'unit': 'ft',
                                 'description': 'Original body separation and following geometry needed to locate the applicable interval.'}],
                'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': [{'name': 'headlamp_gap_ft', 'unit': 'ft',
                                     'description': 'Source-derived following separation over original frames.'}],
                'limitations': ['Original lamp readbacks, pixel visibility, civil time and chapter permissibility need separate source review; this observation defines no legal judgment.']}}


def main():
    refs = {'relevance_batch': write('relevance_batch.json', relevance),
            'relevance': write('relevance.json', relevance),
            'template': write('template.json', template),
            'judgment_observables': [write('judgment_' + str(i + 1) + '.json', observable(*item))
                                     for i, item in enumerate(phrases)],
            'bindings': write('bindings.json', bindings),
            'cases': write('cases.json', semantic_cases)}
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': ASSIGNMENT['assignment_id'],
                                  'stages': refs})


if __name__ == '__main__':
    main()
