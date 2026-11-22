"""Source-bound draft semantic stages for the fixed following assignment."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
assignment = json.loads((REPO/'inputs'/ROOT.name/'assignment.json').read_text())
proposals = ROOT/'proposals'
proposals.mkdir(exist_ok=True)
law = assignment['law']
quote = law['text']
phrase_notes = [
    ('reasonable and prudent', 'The statute supplies no numeric following-distance cutoff.'),
    ('having due regard', 'Both speeds, traffic and highway condition must inform the unresolved judgment.')]


def write(name, value):
    path = proposals/name
    path.write_text(json.dumps(value, indent=2)+'\n')
    return {'path': 'proposals/'+name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


relevance = {'cell_id': assignment['cell_id'], 'actor': assignment['actor'],
    'status': 'draft', 'relevant_laws': [{
        'law_id': assignment['law_id'], 'quote': quote,
        'applies_to': [assignment['actor']],
        'relevance_type': 'direct following-distance duty before lane change',
        'confidence': 'high',
        'notes': 'Fixed branch requests following another vehicle at the hill crest before a lane change.'}],
    'borderline_excluded': []}
refs = {'relevance_batch': write('relevance_batch.json', relevance),
        'relevance': write('relevance.json', relevance)}
cases_path = proposals/'cases.json'
cases = json.loads(cases_path.read_text())
selected = cases['cases'][1]['variable_assignments']
parameters = [(name, item['kind'],
               'Fixed branch or requested physical setup/controller; source-observed, not a legal cutoff')
              for name, item in selected.items()]
if not cases['cases'][0]['variable_assignments']:
    cases['cases'][0]['variable_assignments'] = selected
    cases_path.write_text(json.dumps(cases, indent=2)+'\n')
template = {'template_id': assignment['law_id']+'@'+assignment['actor'],
    'law_id': assignment['law_id'], 'actor': assignment['actor'], 'quote': quote,
    'structure': {'law_id': assignment['law_id'],
        'activation': {'condition': 'A vehicle driver follows another moving vehicle on a highway.',
                       'numeric_conditions': []},
        'obligation': {'description': 'Do not follow more closely than reasonable and prudent, having due regard for both speeds, traffic and highway condition.',
                       'type': 'must', 'numeric_conditions': []},
        'exceptions': [],
        'timing': {'description': 'Measure moving ego and leader in the same lane before the lane change, retaining the original steady interval and transition.',
                   'numeric_conditions': []},
        'judgment_calls_needed': [{'phrase': phrase, 'note': note}
                                  for phrase, note in phrase_notes]},
    'parameter_refs': [{'name': name, 'kind': kind, 'range_or_domain': domain}
                       for name, kind, domain in parameters]}
refs['template'] = write('template.json', template)
channels = [
    ('ego_leader_body_speed_history', 'Original distinct ego/leader bodies and both speeds.'),
    ('traffic_condition_history', 'Original surrounding actor inventory, weather and tire friction.'),
    ('following_lane_history', 'Original road/lane identities and lane-change onset.'),
    ('camera_frame_map', 'Synchronized original camera frame identities.')]
contexts = [
    ('hill_route_context', 'Original connected Native waypoints and hill crest elevation.'),
    ('highway_context', 'Original road/weather context; public-highway status requires review.')]
observables = [{'name': name, 'unit': 'structured record', 'description': description}
               for name, description in channels]
context_inputs = [{'name': name, 'unit': 'structured record', 'description': description}
                  for name, description in contexts]
refs['judgment_observables'] = []
for index, (phrase, note) in enumerate(phrase_notes, 1):
    result = {'template_id': template['template_id'], 'phrase': phrase,
        'note': note, 'status': 'draft',
        'observable_requirements': {
            'observables': observables, 'context_inputs': context_inputs,
            'sweep_dimensions': [
                {'name': name, 'unit': unit, 'description': description}
                for name, unit, description in [
                    ('along_route_body_gap', 'm', 'Source-measured physical spacing.'),
                    ('relative_speed', 'm/s', 'Source-measured speed difference.'),
                    ('surrounding_vehicle_count', 'count', 'Original traffic inventory.'),
                    ('native_precipitation_strength', 'percent', 'Original Native weather and highway condition.')]],
            'landmarks': [], 'recording_needs': observables,
            'limitations': [note, 'Actual Native motion and pixels require independent physical review.']}}
    refs['judgment_observables'].append(write(f'judgment-{index}.json', result))
bindings = {'cell_id': assignment['cell_id'], 'actor': assignment['actor'],
    'status': 'draft',
    'established_contexts': ['hill crest', 'following another moving vehicle', 'lane change after following'],
    'law_refs': [{'template_id': template['template_id'], 'binding_kind': 'direct'}],
    'context_refs': [], 'fixed_parameters': [],
    'variable_parameters': [{'name': name, 'kind': kind,
        'range_or_domain': domain, 'used_by_laws': [assignment['law_id']]}
        for name, kind, domain in parameters]}
refs['bindings'] = write('bindings.json', bindings)
refs['cases'] = {'path': 'proposals/cases.json',
                 'sha256': hashlib.sha256((proposals/'cases.json').read_bytes()).hexdigest()}
write('semantic-index.json', {'format': 'worker-semantic-delivery',
    'assignment_id': assignment['assignment_id'], 'stages': refs})
print('Draft semantic stage chain authored from exact frozen law and cell.')
