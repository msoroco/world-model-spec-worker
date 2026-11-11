"""Author exact-law C10365 officer indication and response proposals."""

from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUT = ROOT / 'proposals'
OUT.mkdir(exist_ok=True)
assignment = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
plan = json.loads((ROOT / 'case-plan.json').read_text())
law, cell, actor = assignment['law'], assignment['cell'], assignment['actor']
aid, law_id, cell_id = assignment['assignment_id'], law['id'], cell['cell_id']
template_id = law_id + '@' + actor
phrase = 'willfully to fail or refuse to comply with any lawful order or direction'
note = ('Original officer indication and subsequent subject motion are measurable; '
        'officer duty, order lawfulness and willfulness require independent source and legal review.')


def write(name, value):
    path = OUT / (name + '.json')
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(ROOT)), 'sha256': sha256(path.read_bytes()).hexdigest()}


relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
    'relevant_laws': [{'law_id': law_id, 'quote': law['text'], 'applies_to': [actor],
        'relevance_type': 'specific_match', 'confidence': 'high',
        'notes': 'Frozen alley travel cell with police officer control; legal predicates remain unresolved.'}],
    'borderline_excluded': []}
refs = {'relevance_batch': write('relevance_batch', relevance),
        'relevance': write('relevance', relevance)}
params = [
    {'name': 'officer_command', 'kind': 'world_setup', 'range_or_domain': 'stop or proceed arm indication'},
    {'name': 'intended_observed_response', 'kind': 'controller',
     'range_or_domain': 'observable response or nonresponse after indication; no willfulness inference'},
    {'name': 'direction_frame', 'kind': 'world_setup',
     'range_or_domain': 'frames 30, 40 or 50 of the 160-frame 20 Hz recording'},
    {'name': 'subject_speed_mps', 'kind': 'subject_behavior',
     'range_or_domain': 'original measured subject velocity, no authored outcome value'}]
template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
    'status': 'draft', 'quote': law['text'],
    'structure': {'law_id': law_id,
        'activation': {'condition': 'A police officer performing traffic-enforcement duties gives a lawful order or direction addressed to the person.',
                       'numeric_conditions': []},
        'obligation': {'type': 'requirement',
                       'description': 'Comply with the lawful order or direction; willful failure or refusal is the prohibited conduct.',
                       'numeric_conditions': []},
        'exceptions': [],
        'timing': {'description': 'Indication precedes enough subsequent subject motion to observe response.',
                   'numeric_conditions': []},
        'judgment_calls_needed': [{'phrase': phrase, 'note': note}]},
    'parameter_refs': params}
refs['template'] = write('template', template)
judgment = {'template_id': template_id, 'phrase': phrase, 'note': note,
    'status': 'draft', 'observable_requirements': {
        'observables': [
            {'name': 'officer_direction', 'unit': 'boolean',
             'description': 'Original timed arm indication and addressed subject identity.'},
            {'name': 'subject_speed_mps', 'unit': 'm/s',
             'description': 'Original post-indication vehicle velocity and motion span.'}],
        'context_inputs': [
            {'name': 'officer_context', 'unit': 'structured record',
             'description': 'Sourced officer identity, duty and order-lawfulness references without legal findings.'},
            {'name': 'officer_direction_context', 'unit': 'structured record',
             'description': 'Addressed subject and timed original pose indication.'}],
        'sweep_dimensions': [
            {'name': 'subject_speed_mps', 'unit': 'm/s',
             'description': 'Original measured post-indication speed under fixed physical indication timing.'},
            {'name': 'officer_command', 'unit': 'enum', 'description': 'Stop versus proceed arm indication.'},
            {'name': 'intended_observed_response', 'unit': 'enum',
             'description': 'Observed response versus nonresponse after indication.'}],
        'landmarks': [],
        'recording_needs': [
            {'name': 'officer_direction', 'unit': 'boolean',
             'description': 'Timed original indication projected to the retained frame interval.'},
            {'name': 'subject_speed_mps', 'unit': 'm/s',
             'description': 'Original subject velocity across the indication and response interval.'}],
        'limitations': ['No fixture establishes lawful duty, lawful order, visibility or willfulness.']}}
refs['judgment_observables'] = [write('judgment_1', judgment)]
binding = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
    'established_contexts': ['alley layout', 'travel maneuver', 'police officer control'],
    'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}], 'context_refs': [],
    'fixed_parameters': [
        {'name': 'cell_layout', 'value': 'alley', 'rationale': 'Frozen catalog cell'},
        {'name': 'cell_maneuver', 'value': 'travel', 'rationale': 'Frozen catalog cell'},
        {'name': 'cell_control', 'value': 'police_officer', 'rationale': 'Frozen catalog cell'}],
    'variable_parameters': [dict(param, used_by_laws=[law_id]) for param in params]}
refs['bindings'] = write('bindings', binding)
description = json.loads((ROOT / 'config.json').read_text())['case']['recording_description']
cases = {'status': 'draft', 'cell_id': cell_id, 'actor': actor,
         'sweep_specs': [{'sweep_id': aid + '__stop_response_window_grid',
             'target_law_id': law_id,
             'judgment_refs': [{'phrase': phrase, 'note': note}],
             'status': 'complete', 'mode': 'one_dimensional',
             'axes': [{'variable': 'direction_frame', 'observable': 'subject_speed_mps',
                 'unit': 'm/s', 'min': 30, 'max': 50, 'spacing': 10,
                 'measurement': {'method': 'original subject velocity sampled after indication',
                                 'time_window': 'post-indication original frames', 'statistic': 'min'},
                 'range_rationale': 'An indication at 1.5, 2.0 or 2.5 seconds leaves distinct fixed observation windows within the eight-second capture; no willfulness cutoff.',
                 'spacing_rationale': 'Three predeclared physical timing settings include both endpoints and one interior point.',
                 'feasibility_evidence': 'The exact Native controller schedules the officer pose and subject control at direction_frame; original pose and speed sources are retained.'}],
             'landmarks': [],
             'rationale': 'Vary the available observation window for a stop indication while keeping the officer, subject and response controller fixed; no lawful-order or willfulness label.',
             'variable_assignments': {
                 'officer_command': {'kind': 'world_setup', 'value': 'stop'},
                 'intended_observed_response': {'kind': 'controller', 'value': 'responds'},
                 'direction_frame': {'kind': 'world_setup', 'value': 40},
                 'subject_speed_mps': {'kind': 'subject_behavior', 'value': None}},
             'recording_description': description}],
         'cases': []}
for planned in plan['cases']:
    case_id = planned['case_id']
    suffix = case_id.split('__')[-1]
    if suffix.startswith('stop_response_window_grid-'):
        continue
    command = 'stop' if suffix.startswith('stop_') else 'proceed'
    response = 'responds' if suffix.endswith('_responds') and 'does_not' not in suffix else 'does_not_respond'
    assignments = {'officer_command': {'kind': 'world_setup', 'value': command},
                   'intended_observed_response': {'kind': 'controller', 'value': response},
                   'direction_frame': {'kind': 'world_setup', 'value': 40},
                   'subject_speed_mps': {'kind': 'subject_behavior', 'value': None}}
    cases['cases'].append({'case_id': case_id, 'target_law_id': law_id,
        'target_type': 'boundary_probe',
        'rationale': 'Observe a timed '+command+' indication followed by '+response+'; no legal or willfulness inference.',
        'variable_assignments': assignments,
        'unresolved_judgment_calls': [phrase],
        'recording_description': description,
        'paired_probe_id': 'stop_response' if command == 'stop' else 'proceed_response',
        'deliberate_differences': ['intended_observed_response'],
        'probe': {'primary_variable': 'intended_observed_response',
                  'comparison_or_standard': 'post-indication original motion contrast',
                  'target_value_or_branch': response}})
baseline = dict(cases['cases'][0], case_id=aid + '__baseline',
                target_law_id=None, target_type='baseline',
                rationale='Shared alley officer and subject setup; no baseline legal result.')
cases['cases'].insert(0, baseline)
import sys
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from batch_pipeline.sweeps import expand_sweeps
expand_sweeps(cases, [template], binding)
refs['cases'] = write('cases', cases)
write('semantic-index', {'format': 'worker-semantic-delivery',
                         'assignment_id': aid, 'stages': refs})
print('Authored four exact C10365 semantic officer-direction cases')
