"""Author the canonical CPU semantic chain and finite exposure sweep."""

import hashlib
import json
from pathlib import Path


root = Path(__file__).resolve().parent
out = root / 'proposals'
assignment = json.loads((root.parents[1] / 'inputs' / root.name / 'assignment.json').read_text())
law, cell, actor = assignment['law'], assignment['cell'], assignment['actor']
law_id, cell_id = law['id'], cell['cell_id']
template_id = law_id + '@' + actor
phrase = 'Such a rate of speed as to endanger the life, limb or property of any person'
note = 'Measure original subject speed, person/property body gap and contact; no numeric legal endangerment threshold is inferred.'


def write(name, value):
    path = out / (name + '.json')
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(root)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
             'relevant_laws': [{'law_id': law_id, 'quote': law['text'],
                                'applies_to': [actor], 'relevance_type': 'specific_match',
                                'confidence': 'high',
                                'notes': 'A narrow-road person exposure cell; property is a fixed test object, with physical and legal fit left for review.'}],
             'borderline_excluded': []}
refs = {'relevance_batch': write('relevance_batch', relevance),
        'relevance': write('relevance', relevance)}

params = [
    {'name': 'requested_speed_mps', 'kind': 'controller',
     'range_or_domain': '2, 5 and 8 m/s engineering targets; no legal speed boundary'},
    {'name': 'outside_edge_m', 'kind': 'world_setup',
     'range_or_domain': '0.4 and 2.0 m engineering lateral placements'},
    {'name': 'exposed_kind', 'kind': 'world_setup',
     'range_or_domain': 'pedestrian or fixed property test object'},
]
template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
            'status': 'draft', 'quote': law['text'],
            'structure': {
                'law_id': law_id,
                'activation': {'condition': 'A person drives or operates a vehicle of any kind or character.',
                               'numeric_conditions': []},
                'obligation': {'type': 'prohibition',
                               'description': 'Do not drive at a rate of speed that endangers any person’s life, limb or property.',
                               'numeric_conditions': []},
                'exceptions': [],
                'timing': {'description': 'Continuous driving rate during the exposure interval.',
                           'numeric_conditions': []},
                'judgment_calls_needed': [{'phrase': phrase, 'note': note}]},
            'parameter_refs': params}
refs['template'] = write('template', template)

judgment = {'template_id': template_id, 'phrase': phrase, 'note': note,
            'status': 'draft', 'observable_requirements': {
                'observables': [
                    {'name': 'ego_speed_mps', 'unit': 'm/s',
                     'description': 'Original subject velocity magnitude over the same exposure interval.'},
                    {'name': 'exposure_gap_m', 'unit': 'm',
                     'description': 'Original subject/exposed body polygon surface gap.'},
                    {'name': 'contact', 'unit': 'boolean',
                     'description': 'Original body polygon intersection; no legal verdict.'}],
                'context_inputs': [],
                'sweep_dimensions': [{'name': 'outside_edge_m', 'unit': 'm',
                                      'description': 'Authored lateral placement relative to the outside lane edge; original body clearance is measured separately.'}],
                'landmarks': [],
                'recording_needs': [{'name': 'exposure_gap_m', 'unit': 'm',
                                     'description': 'Original 20 Hz body polygons carry subject speed, gap and contact.'}],
                'limitations': ['No physical evidence yet establishes requested speed or visibility; legal endangerment remains unresolved.']}}
refs['judgment_observables'] = [write('judgment_1', judgment)]

binding = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
           'established_contexts': ['narrow_road layout', 'travel maneuver', 'person control'],
           'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
           'context_refs': [],
           'fixed_parameters': [
               {'name': 'cell_layout', 'value': 'narrow_road', 'rationale': 'Frozen catalog cell'},
               {'name': 'cell_maneuver', 'value': 'travel', 'rationale': 'Frozen catalog cell'},
               {'name': 'cell_control', 'value': 'person', 'rationale': 'Frozen catalog cell'}],
           'variable_parameters': [dict(param, used_by_laws=[law_id]) for param in params]}
refs['bindings'] = write('bindings', binding)

cases = json.loads((out / 'cases.json').read_text())
cases.pop('format', None)
cases['status'] = 'draft'
cases['cases'] = [case for case in cases['cases']
                  if case['target_type'] not in ('baseline', 'judgment_sweep') and not case['case_id'].endswith('__baseline')]
base = cases['cases'][0]
assignments = base['variable_assignments']
baseline = {'case_id': assignment['assignment_id'] + '__baseline',
            'target_law_id': None, 'target_type': 'baseline',
            'rationale': 'Shared planned narrow-road exposure setup; no baseline delivery or legal result.',
            'variable_assignments': assignments,
            'unresolved_judgment_calls': [phrase],
            'recording_description': base['recording_description']}
for case in cases['cases']:
    case['target_type'] = 'boundary_probe'
    case['unresolved_judgment_calls'] = [phrase]
    case.setdefault('paired_probe_id', 'speed_sweep_low_mid')
    case.setdefault('deliberate_differences', ['requested_speed_mps'])
    case.setdefault('probe', {'primary_variable': 'requested_speed_mps',
                              'comparison_or_standard': 'controlled engineering contrast without legal cutoff',
                              'target_value_or_branch': case['variable_assignments']['requested_speed_mps']['value']})
cases['cases'].insert(0, baseline)
from copy import deepcopy
sweep_assignments = deepcopy(next(c for c in cases['cases']
                                  if c['case_id'].endswith('__moderate_person_exposure'))['variable_assignments'])
sweep_assignments['outside_edge_m']['value'] = 0.6
cases['sweeps_expanded'] = False
cases['sweep_specs'] = [{
    'sweep_id': assignment['assignment_id'] + '__exposure_clearance_sweep',
    'target_law_id': law_id, 'judgment_refs': [{'phrase': phrase, 'note': note}],
    'status': 'complete', 'mode': 'one_dimensional',
    'axes': [{'variable': 'outside_edge_m', 'observable': 'outside_edge_m',
              'unit': 'm', 'min': 0.6, 'max': 1.8, 'spacing': 0.6,
              'measurement': {'method': 'authored selected exterior-placement config',
                              'time_window': 'selected setup', 'statistic': 'first'},
              'range_rationale': 'Existing exact pedestrian placement probes at 0.4 and 2.0 m bound a nonduplicate interior lateral range; actual body clearance is retained from original polygons.',
              'spacing_rationale': 'Three fixed interior placements at 0.6, 1.2 and 1.8 m cover near, middle and farther exposure without a legal cutoff.',
              'feasibility_evidence': 'exposure_case_setup.py places the exposed actor at waypoint 4 (10 m); its exact 0.4/2.0 m offsets and both route directions are CPU tested. The interior offsets use the same spawn geometry.'}],
    'landmarks': [],
    'rationale': 'Finite original-body clearance sampling at fixed 5 m/s requested pedestrian exposure complements the existing 2/5/8 m/s requested-speed comparisons; legal endangerment remains unresolved.',
    'variable_assignments': sweep_assignments,
    'recording_description': deepcopy(base['recording_description'])}]
cases['sweep_specs'][0]['recording_description']['context_inputs'].append({
    'name': 'outside_edge_m', 'unit': 'm',
    'method': 'authored selected exterior-placement config; physical body clearance is measured from original polygons'})
from batch_pipeline.sweeps import expand_sweeps
expand_sweeps(cases, [template], binding)
refs['cases'] = write('cases', cases)
write('semantic-index', {'format': 'worker-semantic-delivery',
                         'assignment_id': assignment['assignment_id'], 'stages': refs})
print('Authored one complete three-point qualitative exposure sweep and nine selected cases')
