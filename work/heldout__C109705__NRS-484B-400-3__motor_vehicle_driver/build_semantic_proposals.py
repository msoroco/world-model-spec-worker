"""Author source-bound draft semantic stages for the three exact turn cases."""

from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'proposals'
OUT.mkdir(exist_ok=True)
assignment = json.loads((ROOT.parents[1] / 'inputs' / ROOT.name / 'assignment.json').read_text())
plan = json.loads((ROOT / 'case-plan.json').read_text())
law, cell, actor = assignment['law'], assignment['cell'], assignment['actor']
aid, law_id, cell_id = assignment['assignment_id'], law['id'], cell['cell_id']
template_id = law_id + '@' + actor
approach_phrase = 'nearest the centerline thereof'
departure_phrase = 'as close as practicable to the left-hand curb of the one-way highway'
phrases = [approach_phrase, departure_phrase]

def write(name, value):
    path = OUT / (name + '.json')
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(ROOT)), 'sha256': sha256(path.read_bytes()).hexdigest()}

relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
    'relevant_laws': [{'law_id': law_id, 'quote': law['text'], 'applies_to': [actor],
        'relevance_type': 'specific_match', 'confidence': 'high',
        'notes': 'The frozen intersection/left-turn/centerline cell matches the express turn branch; physical roadway facts remain to verify.'}],
    'borderline_excluded': []}
refs = {'relevance_batch': write('relevance_batch', relevance),
        'relevance': write('relevance', relevance)}
params = [{'name': 'turn_variant', 'kind': 'controller',
    'range_or_domain': 'centerline approach/left-curb departure, farther approach, or farther departure engineering commands; observed body position remains measured'}]
notes = ['Measure original full-body approach distance from the centerline; the statute supplies no numeric nearest cutoff.',
         'Measure original body distance from the departure left curb and retain roadway feasibility; the statute supplies no numeric practicability cutoff.']
template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
    'status': 'draft', 'quote': law['text'],
    'structure': {'law_id': law_id,
        'activation': {'condition': 'Driver intends a left turn at an intersection from a two-directional highway onto a one-way highway.', 'numeric_conditions': []},
        'obligation': {'type': 'turn_position', 'description': 'Approach in the right half nearest the centerline, enter from its right, and turn as close as practicable to the one-way highway left curb.', 'numeric_conditions': []},
        'exceptions': [], 'timing': {'description': 'Approach, intersection entry, and departure phases.', 'numeric_conditions': []},
        'judgment_calls_needed': [{'phrase': p, 'note': n} for p, n in zip(phrases, notes)]},
    'parameter_refs': params}
refs['template'] = write('template', template)
judgments = []
for index, (phrase, note) in enumerate(zip(phrases, notes), 1):
    judgment = {'template_id': template_id, 'phrase': phrase, 'note': note, 'status': 'draft',
        'observable_requirements': {'observables': [
            {'name': 'turn_centerline_offset', 'unit': 'm', 'description': 'Original body-corner distance from directed approach centerline.'},
            {'name': 'departure_curb_distance', 'unit': 'm', 'description': 'Original body-corner distance from one-way departure left curb.'}],
            'context_inputs': [], 'sweep_dimensions': [
                {'name': 'turn_variant', 'unit': 'categorical', 'description': 'Authored controller variant; original body geometry measured separately.'}],
            'landmarks': [], 'recording_needs': [
                {'name': 'turn_centerline_offset', 'unit': 'm', 'description': 'Full original body-corner offset stream.'}],
            'limitations': ['No Native road-direction or feasible placement proof exists; no legal cutoff is inferred.']}}
    judgments.append(write('judgment_' + str(index), judgment))
refs['judgment_observables'] = judgments
binding = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
    'established_contexts': ['intersection layout', 'left turn', 'centerline control'],
    'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}], 'context_refs': [],
    'fixed_parameters': [
        {'name': 'cell_layout', 'value': 'intersection', 'rationale': 'Frozen cell'},
        {'name': 'cell_maneuver', 'value': 'left_turn', 'rationale': 'Frozen cell'},
        {'name': 'cell_control', 'value': 'centerline', 'rationale': 'Frozen cell'}],
    'variable_parameters': [dict(params[0], used_by_laws=[law_id])]}
refs['bindings'] = write('bindings', binding)
description = json.loads((ROOT / 'cases' / 'construction-centerline_approach_left_curb_departure-primary.json').read_text())['recording_description']
cases = {'status': 'draft', 'cell_id': cell_id, 'actor': actor, 'sweep_specs': [],
         'sweeps_expanded': False, 'cases': []}
for item in plan['cases']:
    case_id = item['case_id']
    suffix = case_id.split('__')[-1]
    group = 'approach_position' if 'farther_approach' in suffix else 'departure_position' if 'farther_departure' in suffix else 'reference'
    cases['cases'].append({'case_id': case_id, 'target_law_id': law_id,
        'target_type': 'boundary_probe', 'rationale': item['purpose'],
        'variable_assignments': {'turn_variant': {'kind': 'controller', 'value': suffix}},
        'unresolved_judgment_calls': phrases, 'recording_description': description,
        'paired_probe_id': group, 'deliberate_differences': ['turn_variant'],
        'probe': {'primary_variable': 'turn_variant',
                  'comparison_or_standard': 'Controlled position contrast with no statutory distance threshold',
                  'target_value_or_branch': suffix}})
baseline = dict(cases['cases'][0], case_id=aid + '__baseline', target_law_id=None,
                target_type='baseline', rationale='Shared selected turn setup; no baseline delivery result.')
cases['cases'].insert(0, baseline)
for index, (phrase, note) in enumerate(zip(phrases, notes), 1):
    cases['sweep_specs'].append({'sweep_id': f'{aid}__turn_judgment_{index}',
        'target_law_id': law_id, 'judgment_refs': [{'phrase': phrase, 'note': note}],
        'status': 'incomplete',
        'missing_inputs': ['Verified Native two-directional/one-way connected roadway and physical feasible lateral range for a finite sweep'],
        'rationale': 'An actual feasible lateral range and spacing must be surveyed before selecting judgment sweep setpoints.'})
from batch_pipeline.sweeps import expand_sweeps
expand_sweeps(cases, [template], binding)
refs['cases'] = write('cases', cases)
write('semantic-index', {'format': 'worker-semantic-delivery', 'assignment_id': aid, 'stages': refs})
print('Draft semantic stages: three ordinary turn cases and two explicitly incomplete Native-feasibility sweeps')

if __name__ == '__main__':
    pass
