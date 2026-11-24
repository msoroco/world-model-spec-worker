"""Author the frozen-law draft semantic chain for the two selected CPU requests."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / 'proposals'
ASSIGNMENT = json.loads((REPO / 'inputs' / HERE.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']
LAW_ID = ASSIGNMENT['law_id']
ACTOR = ASSIGNMENT['actor']
CELL = ASSIGNMENT['cell_id']
TID = LAW_ID + '@' + ACTOR
QUOTE = LAW['text']
RECORDING = json.loads((HERE / 'construction.json').read_text())['recording_description']


def emit(name, value):
    path = OUT / (name + '.json')
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


relevance = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
             'relevant_laws': [{'law_id': LAW_ID,
                                'quote': QUOTE.split(' A person who violates')[0],
                                'applies_to': [ACTOR], 'relevance_type': 'specific_match',
                                'confidence': 'medium',
                                'notes': 'Sidewalk control in the frozen cell; exact City area and statutory exceptions require source review.'}],
             'borderline_excluded': []}
refs = {'relevance_batch': emit('relevance_batch', relevance),
        'relevance': emit('relevance', relevance)}
template = {'template_id': TID, 'law_id': LAW_ID, 'actor': ACTOR, 'status': 'draft',
            'quote': QUOTE,
            'structure': {
                'law_id': LAW_ID,
                'activation': {'condition': 'The driver of a vehicle drives upon or within a sidewalk area.',
                               'source_clause': 'the driver of a vehicle shall not drive upon or within any sidewalk area',
                               'numeric_conditions': []},
                'obligation': {'type': 'must_not',
                               'description': 'Do not drive upon or within a sidewalk area outside the stated entrances and subsection 2 exception.',
                               'source_clause': 'shall not drive upon or within any sidewalk area',
                               'numeric_conditions': []},
                'exceptions': [
                    {'trigger': 'At a permanent or temporary driveway or alley entrance',
                     'effect': 'The sidewalk-area prohibition does not apply at that entrance.',
                     'replacement_obligation': None,
                     'source_clause': 'except at a permanent or temporary driveway or alley entrance'},
                    {'trigger': 'Solely electric three-wheel vehicle operated as an authorized emergency vehicle',
                     'effect': 'Subsection 1 does not apply when subsection 2 conditions are met.',
                     'replacement_obligation': None,
                     'source_clause': '(a) As an authorized emergency vehicle;'},
                    {'trigger': 'Solely electric three-wheel vehicle operated by an authorized law-enforcement employee on duty',
                     'effect': 'Subsection 1 does not apply when subsection 2 conditions are met.',
                     'replacement_obligation': None,
                     'source_clause': '(b) By an officer or other authorized employee of a law enforcement agency, as that term is defined in NRS 239C.065, in the course of his or her official duties;'},
                    {'trigger': 'Solely electric three-wheel vehicle operated by a security guard on duty',
                     'effect': 'Subsection 1 does not apply when subsection 2 conditions are met.',
                     'replacement_obligation': None,
                     'source_clause': '(c) By a security guard, as that term is defined in NRS 648.016, in the course of his or her official duties.'},
                ],
                'timing': {'description': 'During the observed driving in the sidewalk area.',
                           'numeric_conditions': []},
                'judgment_calls_needed': []},
            'parameter_refs': []}
refs['template'] = emit('template', template)
refs['judgment_observables'] = []
parameters = [
    {'name': 'road_and_actors', 'kind': 'world_setup',
     'range_or_domain': 'two-way two-lane road, source-qualified sidewalk and heavy vehicle',
     'used_by_laws': [LAW_ID]},
    {'name': 'entrance_and_exception_context', 'kind': 'world_setup',
     'range_or_domain': 'City entrance designation, vehicle propulsion/wheel design and operator duty; unresolved until sourced',
     'used_by_laws': [LAW_ID]},
    {'name': 'commanded_lateral_target', 'kind': 'controller',
     'range_or_domain': 'road-travel or authored sidewalk-overlap request in m',
     'used_by_laws': [LAW_ID]},
    {'name': 'commanded_approach_speed', 'kind': 'controller',
     'range_or_domain': '4 m/s requested; original measured speed independent',
     'used_by_laws': [LAW_ID]},
    {'name': 'ego_speed', 'kind': 'subject_behavior',
     'range_or_domain': 'original measured speed in m/s', 'used_by_laws': [LAW_ID]},
    {'name': 'drive_within_sidewalk_area', 'kind': 'subject_behavior',
     'range_or_domain': 'measured body overlap with source-qualified sidewalk area',
     'used_by_laws': [LAW_ID]},
]
binding = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
           'established_contexts': [{'name': 'frozen_cell',
                                     'source': 'frozen two_lane_two_way/travel/sidewalk catalog cell'}],
           'law_refs': [{'template_id': TID, 'binding_kind': 'direct'}],
           'context_refs': [], 'fixed_parameters': [], 'variable_parameters': parameters}
refs['bindings'] = emit('bindings', binding)


def values(lateral):
    return {'road_and_actors': {'kind': 'world_setup', 'value': 'authored two-lane road and heavy vehicle'},
            'entrance_and_exception_context': {'kind': 'world_setup', 'value': 'unverified; fail closed'},
            'commanded_lateral_target': {'kind': 'controller', 'value': lateral, 'unit': 'm'},
            'commanded_approach_speed': {'kind': 'controller', 'value': 4.0, 'unit': 'm/s'},
            'ego_speed': {'kind': 'subject_behavior', 'value': None},
            'drive_within_sidewalk_area': {'kind': 'subject_behavior', 'value': None}}


cases = [{'case_id': HERE.name + '__baseline', 'target_law_id': None,
          'target_type': 'baseline', 'rationale': 'Shared authored geometry and source review; no baseline recording selected.',
          'variable_assignments': values(1.75), 'recording_description': RECORDING,
          'unresolved_judgment_calls': []}]
for suffix, target, lateral in [('reference', 'compliant_attempt', 1.75),
                                ('contrast', 'violating_attempt', 4.7)]:
    cases.append({'case_id': HERE.name + '__' + suffix, 'target_law_id': LAW_ID,
                  'target_type': target, 'status': 'draft',
                  'rationale': 'Requested road/sidewalk body-overlap comparison only; legal classification waits for original City and exception evidence.',
                  'variable_assignments': values(lateral), 'recording_description': RECORDING,
                  'unresolved_judgment_calls': [], 'paired_probe_id': HERE.name + '__sidewalk_pair',
                  'deliberate_differences': ['commanded_lateral_target'],
                  'probe': {'primary_variable': 'commanded_lateral_target',
                            'comparison_or_standard': 'road travel versus sidewalk overlap request',
                            'target_value_or_branch': suffix}})
canonical = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
             'sweep_specs': [], 'cases': cases}
refs['cases'] = emit('canonical-cases', canonical)
emit('semantic-index', {'format': 'worker-semantic-delivery',
                        'assignment_id': HERE.name, 'stages': refs})
print('authored canonical semantic chain')
