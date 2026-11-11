"""Author canonical, source-hashed C10364 alley semantic proposals."""

from hashlib import sha256
import json
from pathlib import Path


root = Path(__file__).resolve().parent
out = root / 'proposals'
out.mkdir(exist_ok=True)
assignment = json.loads((root.parents[1] / 'inputs' / root.name / 'assignment.json').read_text())
plan = json.loads((root / 'case-plan.json').read_text())
law, cell, actor = assignment['law'], assignment['cell'], assignment['actor']
aid, law_id, cell_id = assignment['assignment_id'], law['id'], cell['cell_id']
template_id = law_id + '@' + actor
phrase = 'Such a rate of speed as to endanger the life, limb or property of any person'
note = ('Measure original speed, pedestrian/property body gaps, contact, forward-time '
        'and braking proxies; no numeric legal endangerment threshold is inferred.')


def write(name, value):
    path = out / (name + '.json')
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(root)),
            'sha256': sha256(path.read_bytes()).hexdigest()}


relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
    'relevant_laws': [{'law_id': law_id, 'quote': law['text'],
        'applies_to': [actor], 'relevance_type': 'specific_match',
        'confidence': 'high', 'notes': 'Alley travel with a stationary person and owned property; physical and legal fit remain for review.'}],
    'borderline_excluded': []}
refs = {'relevance_batch': write('relevance_batch', relevance),
        'relevance': write('relevance', relevance)}
params = [
    {'name': 'target_speed_mps', 'kind': 'controller',
     'range_or_domain': '3, 5 and 7 m/s engineering targets; no legal speed boundary'},
    {'name': 'protected_interest', 'kind': 'world_setup',
     'range_or_domain': 'stationary pedestrian life/limb or that person’s owned property'},
    {'name': 'alley_direction', 'kind': 'world_setup',
     'range_or_domain': 'east selected route; west is a construction fallback'},
]
template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
    'status': 'draft', 'quote': law['text'],
    'structure': {'law_id': law_id,
        'activation': {'condition': 'A person drives or operates a vehicle of any kind or character.',
                       'numeric_conditions': []},
        'obligation': {'type': 'prohibition',
                       'description': 'Do not drive at a rate of speed that endangers any person’s life, limb or property.',
                       'numeric_conditions': []},
        'exceptions': [],
        'timing': {'description': 'Continuous driving rate during alley exposure.',
                   'numeric_conditions': []},
        'judgment_calls_needed': [{'phrase': phrase, 'note': note}]},
    'parameter_refs': params}
refs['template'] = write('template', template)
judgment = {'template_id': template_id, 'phrase': phrase, 'note': note,
    'status': 'draft', 'observable_requirements': {
        'observables': [
            {'name': 'ego_speed_mps', 'unit': 'm/s', 'description': 'Original subject footprint-center speed over exposure interval.'},
            {'name': 'pedestrian_gap_m', 'unit': 'm', 'description': 'Original subject/pedestrian body polygon surface gap.'},
            {'name': 'property_gap_m', 'unit': 'm', 'description': 'Original subject/owned-property body polygon surface gap.'},
            {'name': 'contact', 'unit': 'boolean', 'description': 'Original body polygon intersection; no legal verdict.'}],
        'context_inputs': [],
        'sweep_dimensions': [{'name': 'target_speed_mps', 'unit': 'm/s',
            'description': 'Engineering requested-speed contrast; original realized speed is measured separately.'}],
        'landmarks': [],
        'recording_needs': [{'name': 'participant_footprints', 'unit': 'structured record',
            'description': 'Original 20 Hz ego, pedestrian and property body polygons with Native motion and camera frame map.'}],
        'limitations': ['No Native exposure or camera visibility is established; statutory endangerment remains unresolved.']}}
refs['judgment_observables'] = [write('judgment_1', judgment)]
binding = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
    'established_contexts': ['alley layout', 'travel maneuver', 'person control'],
    'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
    'context_refs': [],
    'fixed_parameters': [
        {'name': 'cell_layout', 'value': 'alley', 'rationale': 'Frozen catalog cell'},
        {'name': 'cell_maneuver', 'value': 'travel', 'rationale': 'Frozen catalog cell'},
        {'name': 'cell_control', 'value': 'person', 'rationale': 'Frozen catalog cell'}],
    'variable_parameters': [dict(param, used_by_laws=[law_id]) for param in params]}
refs['bindings'] = write('bindings', binding)
description = {'channels': [{
    'name': 'participant_footprints', 'unit': 'structured record',
    'method': 'original Native ego, pedestrian and owned-property body polygons',
    'sampling_rate_hz': 20, 'time_window': 'all original frames',
    'reference_frame': 'world ground plane',
    'uncertainty': 'Native actor bounding-box precision'},
    *[
    {'name': kind + '_gap_m', 'unit': 'm',
     'method': 'original Native subject/' + kind + ' body polygon distance',
     'sampling_rate_hz': 20, 'time_window': 'all original frames',
     'reference_frame': 'world ground plane',
     'uncertainty': 'Native body bounding-box precision'}
    for kind in ('pedestrian', 'property')]],
    'context_inputs': [],
    'limitations': ['Engineering speed targets and alley placements do not establish legal endangerment, visibility or completion.']}
cases = {'status': 'draft', 'cell_id': cell_id, 'actor': actor,
         'sweep_specs': [], 'sweeps_expanded': False, 'cases': []}
for planned in plan['cases']:
    case_id = planned['case_id']
    case = planned['construction']
    speed = case['target_speed_mps']
    interest = case['protected_interest']
    assignments = {'target_speed_mps': {'kind': 'controller', 'value': speed},
                   'protected_interest': {'kind': 'world_setup', 'value': interest},
                   'alley_direction': {'kind': 'world_setup', 'value': 'east'}}
    cases['cases'].append({'case_id': case_id, 'target_law_id': law_id,
        'target_type': 'boundary_probe',
        'rationale': f'Measure original {interest} exposure during {speed:g} m/s requested alley travel; legal judgment unresolved.',
        'variable_assignments': assignments,
        'unresolved_judgment_calls': [phrase],
        'recording_description': description,
        'paired_probe_id': interest + '_speed_sweep',
        'deliberate_differences': ['target_speed_mps'],
        'probe': {'primary_variable': 'target_speed_mps',
                  'comparison_or_standard': 'controlled engineering contrast without legal cutoff',
                  'target_value_or_branch': speed}})
baseline = dict(cases['cases'][0], case_id=aid + '__baseline',
                target_law_id=None, target_type='baseline',
                rationale='Shared planned alley setup; no baseline delivery or legal result.')
cases['cases'].insert(0, baseline)
cases['sweep_specs'] = [{
    'sweep_id': aid + '__alley_speed_judgment_sweep',
    'target_law_id': law_id, 'judgment_refs': [{'phrase': phrase, 'note': note}],
    'status': 'incomplete', 'mode': 'one_dimensional',
    'axes': [{'variable': 'target_speed_mps', 'observable': 'target_speed_mps',
        'unit': 'm/s', 'min': 3, 'max': 7, 'spacing': 2,
        'measurement': {'method': 'authored controller target; original realized speed measured separately',
                        'time_window': 'selected setup', 'statistic': 'first'},
        'range_rationale': 'The three planned 3/5/7 m/s engineering contrasts bracket a moderate alley speed without creating a legal cutoff.',
        'spacing_rationale': 'Two m/s spacing gives low, middle and high requested-speed points.',
        'feasibility_evidence': 'alley_route.control_step and alley_geometry.plan_alley pass CPU tests; selected source-backed alley geometry remains unconstructed.'}],
    'landmarks': [],
    'rationale': 'Finite requested-speed judgment sampling must be bound to a selected source-backed alley route and original measured motion.',
    'variable_assignments': dict(cases['cases'][1]['variable_assignments']),
    'recording_description': description,
    'missing_inputs': ['Selected original alley polygon and exact Native route source are absent; generated cases and physical feasibility proofs remain CPU construction work.']}]
refs['cases'] = write('cases', cases)
write('semantic-index', {'format': 'worker-semantic-delivery',
                         'assignment_id': aid, 'stages': refs})
print('Authored six selected alley semantic cases and one planning baseline')
