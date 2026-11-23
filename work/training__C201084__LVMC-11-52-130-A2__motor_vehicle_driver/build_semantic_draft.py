"""Write source-faithful draft semantic stages for eight CPU probes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROPOSALS = HERE/'proposals'
ASSIGNMENT = HERE.name
LAW = 'LVMC-11-52-130-A2'
CELL = 'C201084'
ACTOR = 'motor_vehicle_driver'
TEMPLATE = LAW+'@'+ACTOR
PAIR = ASSIGNMENT+'__comparison_main'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2)+'\n')


def build():
    assignment = json.loads((ROOT/'inputs'/ASSIGNMENT/'assignment.json').read_text())
    law_text = assignment['law']['text']
    reference = json.loads((HERE/'draft-reference-fallback-manifest.json').read_text())['cases'][0]
    contrast = json.loads((HERE/'draft-contrast-fallback-manifest.json').read_text())['cases'][0]
    conflict = json.loads((HERE/'draft-conflict-fallback-manifest.json').read_text())['cases'][0]
    clear = json.loads((HERE/'draft-clear-fallback-manifest.json').read_text())['cases'][0]
    near = json.loads((HERE/'draft-near_lead-fallback-manifest.json').read_text())['cases'][0]
    absent = json.loads((HERE/'draft-absent_lead-fallback-manifest.json').read_text())['cases'][0]
    device = json.loads((HERE/'draft-device-direction-fallback-manifest.json').read_text())['cases'][0]
    officer = json.loads((HERE/'draft-officer-direction-fallback-manifest.json').read_text())['cases'][0]
    recording = json.loads((HERE/reference['construction']).read_text())['recording_description']
    assert recording == json.loads((HERE/contrast['construction']).read_text())['recording_description']
    conflict_recording = json.loads((HERE/conflict['construction']).read_text())['recording_description']
    clear_recording = json.loads((HERE/clear['construction']).read_text())['recording_description']
    near_recording = json.loads((HERE/near['construction']).read_text())['recording_description']
    absent_recording = json.loads((HERE/absent['construction']).read_text())['recording_description']
    device_recording = json.loads((HERE/device['construction']).read_text())['recording_description']
    officer_recording = json.loads((HERE/officer['construction']).read_text())['recording_description']
    relevance = {'status': 'draft', 'actor': ACTOR, 'cell_id': CELL,
                 'borderline_excluded': [], 'relevant_laws': [{
                     'law_id': LAW, 'applies_to': [ACTOR], 'confidence': 'medium',
                     'relevance_type': 'specific_match', 'quote': law_text,
                     'notes': 'The fire-lane destination stop is a physical coverage probe; posting, designation and exception facts need original source review.'}]}
    write(PROPOSALS/'relevance.json', relevance)
    write(PROPOSALS/'relevance_batch.json', relevance)
    judgments = [
        ('designated and posted as a fire lane pursuant to the City\'s Fire Code',
         'Authored geometry and a sign actor do not verify posting text or City Fire Code designation.',
         'ego_pose', 'Source-joined pose and footprint locate the stopped vehicle; original sign pixels and designation remain to be reviewed.'),
        ('necessary to avoid conflict with other traffic',
         'The lead probe samples a traffic relation and brake request but does not establish statutory necessity.',
         'ego_speed', 'Saved ego speed locates the stop in every case; the lead-presence pair additionally records an actor inventory. Necessity and compliance require original review.'),
        ('in compliance with law',
         'An applicable source of law and the reason for the stop are not supplied by synthetic motion.',
         'ego_pose', 'Source pose locates the vehicle; applicable law must be reviewed independently.'),
        ('the directions of a police officer or a traffic control device',
         'The fire-lane sign is not evidence of a police direction. Device and pedestrian-actor probes retain source state and pose; authority, applicability and necessity need original review.',
         'ego_speed', 'Source speed locates the stop; device and actor probes add source-joined context, while authority, direction applicability and response need original evidence.'),
    ]
    template = {'status': 'draft', 'law_id': LAW, 'actor': ACTOR,
                'template_id': TEMPLATE, 'quote': law_text, 'parameter_refs': [],
                'structure': {
                    'activation': {'description': 'A vehicle stops, stands or parks in a qualifying posted fire-lane curb place or space.',
                                   'source_clause': "At any place or in any space adjacent to a curb which has been designated and posted as a fire lane pursuant to the City's Fire Code"},
                    'obligation': {'type': 'prohibition', 'description': 'Do not stop, stand or park there unless a stated exception applies.',
                                   'source_clause': 'No person shall stop, stand or park a vehicle'},
                    'exceptions': [
                        {'description': 'Potential stop-necessity exception context; exact interaction with following compliance language requires source review.',
                         'source_clause': 'when necessary to avoid conflict with other traffic'},
                        {'description': 'Potential applicable-law exception context; clause relationship requires source review.',
                         'source_clause': 'in compliance with law'},
                        {'description': 'Potential police or traffic-control direction context; clause relationship requires source review.',
                         'source_clause': 'the directions of a police officer or a traffic control device'}],
                    'timing': {'description': 'Measure the original source continuously through the attempted halt and keep exception evidence time aligned.'},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note}
                                              for phrase, note, _, _ in judgments]}}
    write(PROPOSALS/'template.json', template)
    for i,(phrase,note,channel,description) in enumerate(judgments):
        unit = next(row['unit'] for row in recording['channels'] if row['name'] == channel)
        value = {'status': 'draft', 'template_id': TEMPLATE,
                 'phrase': phrase, 'note': note,
                 'observable_requirements': {
                     'observables': [{'name': channel, 'unit': unit,
                                      'description': description}],
                     'context_inputs': [{'name': 'original_map_sign_and_fire_lane_survey',
                                         'unit': 'structured',
                                         'description': 'Retain map, sign and authored curb context with original provenance.'}],
                     'sweep_dimensions': [], 'landmarks': [],
                     'recording_needs': [{'name': channel, 'unit': unit,
                                          'description': description}],
                     'limitations': [note, 'Current diagnostic probes do not resolve this legal judgment.']}}
        write(PROPOSALS/f'judgment_observables_{i}.json', value)
    bindings = {'status': 'draft', 'actor': ACTOR, 'cell_id': CELL,
                'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
                'context_refs': [], 'established_contexts': [], 'fixed_parameters': [],
                'variable_parameters': [
                    {'name': 'requested_stop_destination', 'kind': 'controller',
                     'range_or_domain': 'inside or outside the authored curb zone',
                     'used_by_laws': [LAW]},
                    {'name': 'actual_stop_zone_relation', 'kind': 'subject_behavior',
                     'range_or_domain': 'source-observed overlap or disjoint relation',
                     'used_by_laws': [LAW]},
                    {'name': 'lead_traffic_conflict_probe', 'kind': 'controller',
                     'range_or_domain': 'lead near, lead beyond authored segment, or absent on surveyed road',
                     'used_by_laws': [LAW]},
                    {'name': 'lead_traffic_presence', 'kind': 'controller',
                     'range_or_domain': 'lead at x=18 m or no lead actor at shared destination',
                     'used_by_laws': [LAW]},
                    {'name': 'traffic_control_device_state', 'kind': 'world_setup',
                     'range_or_domain': 'source-observed traffic-light state throughout the attempted stop',
                     'used_by_laws': [LAW]},
                    {'name': 'police_officer_actor_pose', 'kind': 'world_setup',
                     'range_or_domain': 'source-observed pedestrian identity, pose and velocity; police authority unverified',
                     'used_by_laws': [LAW]}]}
    write(PROPOSALS/'bindings.json', bindings)
    cases = []
    for suffix, destination in (('reference', 'inside'), ('contrast', 'outside')):
        cases.append({'case_id': ASSIGNMENT+'__'+suffix, 'target_law_id': LAW,
                      'target_type': 'judgment_sweep', 'paired_probe_id': PAIR,
                      'deliberate_differences': ['requested_stop_destination'],
                      'probe': {'primary_variable': 'requested_stop_destination',
                                'comparison_or_standard': 'sampled authored-zone stop relation; statutory judgment unresolved',
                                'target_value_or_branch': {'requested_stop_destination': destination}},
                      'rationale': 'Request the '+destination+'-zone stop in the same surveyed scene.',
                      'variable_assignments': {
                          'requested_stop_destination': {'kind': 'controller', 'value': destination},
                          'actual_stop_zone_relation': {'kind': 'subject_behavior', 'value': None},
                          'lead_traffic_conflict_probe': {'kind': 'controller', 'value': 'absent'}},
                      'recording_description': recording,
                      'unresolved_judgment_calls': [phrase for phrase,_,_,_ in judgments]})
    cases.append({'case_id': ASSIGNMENT+'__conflict', 'target_law_id': LAW,
                  'target_type': 'judgment_sweep',
                  'paired_probe_id': ASSIGNMENT+'__lead_position_pair',
                  'deliberate_differences': ['lead_traffic_conflict_probe'],
                  'probe': {'primary_variable': 'lead_traffic_conflict_probe',
                            'comparison_or_standard': 'saved lead position, velocity and braking request; statutory necessity unresolved',
                            'target_value_or_branch': {'lead_traffic_conflict_probe': 'lead at x=18 m'}},
                  'rationale': 'Record a same-road lead vehicle ahead during the authored-zone stop.',
                  'variable_assignments': {
                      'requested_stop_destination': {'kind': 'controller', 'value': 'inside'},
                      'actual_stop_zone_relation': {'kind': 'subject_behavior', 'value': None},
                      'lead_traffic_conflict_probe': {'kind': 'controller', 'value': 'lead at x=18 m'}},
                  'recording_description': conflict_recording,
                  'unresolved_judgment_calls': [phrase for phrase,_,_,_ in judgments]})
    cases.append({'case_id': ASSIGNMENT+'__clear', 'target_law_id': LAW,
                  'target_type': 'judgment_sweep',
                  'paired_probe_id': ASSIGNMENT+'__lead_position_pair',
                  'deliberate_differences': ['lead_traffic_conflict_probe'],
                  'probe': {'primary_variable': 'lead_traffic_conflict_probe',
                            'comparison_or_standard': 'saved lead position and initial braking request; statutory necessity unresolved',
                            'target_value_or_branch': {'lead_traffic_conflict_probe': 'lead at x=35 m'}},
                  'rationale': 'Move the same-road lead beyond the authored fire-lane segment with the same controller and capture.',
                  'variable_assignments': {
                      'requested_stop_destination': {'kind': 'controller', 'value': 'inside'},
                      'actual_stop_zone_relation': {'kind': 'subject_behavior', 'value': None},
                      'lead_traffic_conflict_probe': {'kind': 'controller', 'value': 'lead at x=35 m'}},
                  'recording_description': clear_recording,
                  'unresolved_judgment_calls': [phrase for phrase,_,_,_ in judgments]})
    for suffix, present, description in (
            ('near_lead', True, 'same-road lead at x=18 m'),
            ('absent_lead', False, 'no lead actor')):
        cases.append({'case_id': ASSIGNMENT+'__'+suffix, 'target_law_id': LAW,
                      'target_type': 'judgment_sweep',
                      'paired_probe_id': ASSIGNMENT+'__lead_presence_pair',
                      'deliberate_differences': ['lead_traffic_presence'],
                      'probe': {'primary_variable': 'lead_traffic_presence',
                                'comparison_or_standard': 'saved actor inventory and control requests; statutory necessity unresolved',
                                'target_value_or_branch': {'lead_traffic_presence': present}},
                      'rationale': 'At the shared x=30 m destination, record '+description+' under one controller.',
                      'variable_assignments': {
                          'requested_stop_destination': {'kind': 'controller', 'value': 'x=30 m beyond authored zone'},
                          'actual_stop_zone_relation': {'kind': 'subject_behavior', 'value': None},
                          'lead_traffic_conflict_probe': {'kind': 'controller', 'value': 'optional source-observed lead under common controller'},
                          'lead_traffic_presence': {'kind': 'controller', 'value': present}},
                      'recording_description': near_recording if present else absent_recording,
                      'unresolved_judgment_calls': [phrase for phrase,_,_,_ in judgments]})
    cases.append({'case_id': ASSIGNMENT+'__device_direction',
                  'target_law_id': LAW, 'target_type': 'judgment_sweep',
                  'paired_probe_id': ASSIGNMENT+'__device_direction_probe',
                  'deliberate_differences': ['traffic_control_device_state'],
                  'probe': {'primary_variable': 'traffic_control_device_state',
                            'comparison_or_standard': 'saved per-frame light state; direction applicability and statutory necessity unresolved',
                            'target_value_or_branch': {'traffic_control_device_state': 'source-observed'}},
                  'rationale': 'Retain original traffic-light state during the authored-zone stop without a legal conclusion.',
                  'variable_assignments': {
                      'requested_stop_destination': {'kind': 'controller', 'value': 'inside'},
                      'actual_stop_zone_relation': {'kind': 'subject_behavior', 'value': None},
                      'lead_traffic_conflict_probe': {'kind': 'controller', 'value': 'absent'},
                      'lead_traffic_presence': {'kind': 'controller', 'value': False},
                      'traffic_control_device_state': {'kind': 'world_setup', 'value': 'source-observed traffic light'}},
                  'recording_description': device_recording,
                  'unresolved_judgment_calls': [phrase for phrase,_,_,_ in judgments]})
    cases.append({'case_id': ASSIGNMENT+'__officer_direction',
                  'target_law_id': LAW, 'target_type': 'judgment_sweep',
                  'paired_probe_id': ASSIGNMENT+'__officer_direction_probe',
                  'deliberate_differences': ['police_officer_actor_pose'],
                  'probe': {'primary_variable': 'police_officer_actor_pose',
                            'comparison_or_standard': 'saved per-frame pedestrian pose; police authority, direction applicability and necessity unresolved',
                            'target_value_or_branch': {'police_officer_actor_pose': 'source-observed'}},
                  'rationale': 'Retain a surveyed pedestrian actor during the authored-zone stop without a police-authority or legal conclusion.',
                  'variable_assignments': {
                      'requested_stop_destination': {'kind': 'controller', 'value': 'inside'},
                      'actual_stop_zone_relation': {'kind': 'subject_behavior', 'value': None},
                      'lead_traffic_conflict_probe': {'kind': 'controller', 'value': 'absent'},
                      'lead_traffic_presence': {'kind': 'controller', 'value': False},
                      'police_officer_actor_pose': {'kind': 'world_setup', 'value': 'source-observed pedestrian'}},
                  'recording_description': officer_recording,
                  'unresolved_judgment_calls': [phrase for phrase,_,_,_ in judgments]})
    cases.insert(0, {'case_id': ASSIGNMENT+'__baseline', 'target_law_id': None,
                     'target_type': 'baseline', 'rationale': 'Common source-surveyed fire-lane context.',
                     'variable_assignments': {
                         'requested_stop_destination': {'kind': 'controller', 'value': 'shared survey'},
                         'actual_stop_zone_relation': {'kind': 'subject_behavior', 'value': None},
                         'lead_traffic_conflict_probe': {'kind': 'controller', 'value': 'absent'}},
                     'recording_description': recording,
                     'unresolved_judgment_calls': [phrase for phrase,_,_,_ in judgments]})
    for item in cases:
        suffix = item['case_id'].rsplit('__', 1)[-1]
        item['variable_assignments'].setdefault('lead_traffic_presence',
            {'kind': 'controller',
             'value': suffix in ('conflict', 'clear', 'near_lead')})
        item['variable_assignments'].setdefault('traffic_control_device_state',
            {'kind': 'world_setup', 'value': 'not separately inventoried'})
        item['variable_assignments'].setdefault('police_officer_actor_pose',
            {'kind': 'world_setup', 'value': 'not separately inventoried'})
    canonical = {'status': 'draft', 'actor': ACTOR, 'cell_id': CELL,
                 'cases': cases, 'sweeps_expanded': True,
                 'sweep_specs': [{'sweep_id': 'fire_lane_exception_scope_pending',
                                 'target_law_id': LAW,
                                 'judgment_refs': [{'phrase': phrase, 'note': note}
                                                   for phrase,note,_,_ in judgments],
                                 'rationale': 'Inside/outside, lead and light-state diagnostic probes are built; posting and remaining statutory routes are unresolved.',
                                 'status': 'incomplete',
                                 'missing_inputs': ['Original City Fire Code designation and posting evidence',
                                                    'Original conflict causation review',
                                                    'Applicable-law direction source',
                                                    'Original pedestrian authority and direction review',
                                                    'Original traffic-light applicability and stop-direction review',
                                                    'Attendance and public/private property source review']}],
                 'unselected_statutory_routes': ['conflict necessity', 'applicable-law compliance',
                                                  'police direction applicability', 'traffic-control device direction',
                                                  'standing or parking', 'attendance and property contexts']}
    write(PROPOSALS/'canonical-cases.json', canonical)
    stages = {}
    for stage, name in (('relevance_batch','relevance_batch.json'),
                        ('relevance','relevance.json'), ('template','template.json'),
                        ('bindings','bindings.json'), ('cases','canonical-cases.json')):
        path = PROPOSALS/name
        stages[stage] = {'path': str(path.relative_to(HERE)), 'sha256': sha(path)}
    stages['judgment_observables'] = [
        {'path': str((PROPOSALS/f'judgment_observables_{i}.json').relative_to(HERE)),
         'sha256': sha(PROPOSALS/f'judgment_observables_{i}.json')}
        for i in range(len(judgments))]
    write(PROPOSALS/'semantic-index.json',
          {'format': 'worker-semantic-delivery', 'assignment_id': ASSIGNMENT,
           'stages': stages})
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': ASSIGNMENT, 'status': 'draft_semantic_validation_only',
                'cases': [reference, contrast, conflict, clear, near, absent, device, officer]}
    write(HERE/'draft-semantic-manifest.json', manifest)
    return {'semantic_index_sha256': sha(PROPOSALS/'semantic-index.json'),
            'draft_manifest_sha256': sha(HERE/'draft-semantic-manifest.json'),
            'selected_cpu_probe_cases': 8, 'unresolved_judgments': len(judgments)}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
