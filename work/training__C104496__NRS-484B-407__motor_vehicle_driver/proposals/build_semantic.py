"""Author source-bound draft semantics for the frozen C104496 law and cell."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ASSIGNMENT = 'training__C104496__NRS-484B-407__motor_vehicle_driver'
LAW = json.loads((ROOT / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())['law']
LAW_ID, ACTOR, CELL = LAW['id'], 'motor_vehicle_driver', 'C104496'
TEMPLATE = LAW_ID + '@' + ACTOR


def put(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def author():
    relevance = {
        'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{
            'law_id': LAW_ID,
            'quote': 'A vehicle shall not be turned so as to proceed in the opposite direction upon any curve, or upon the approach to or near the crest of a grade, where such vehicle cannot be seen by the driver of any other vehicle approaching from either direction within 500 feet.',
            'applies_to': [ACTOR], 'relevance_type': 'direct', 'confidence': 'high',
            'notes': 'Frozen hill_crest/u_turn cell directly supports the crest and reversal setting. The authored curve variant is a separate controlled geometric comparison; actual Native visibility remains unknown.'
        }], 'borderline_excluded': []}
    put('relevance.json', relevance)
    put('relevance-batch.json', relevance)
    judgments = [
        ('upon any curve', 'Review generated plan-view curvature and the complete physical reversal interval.'),
        ('upon the approach to or near the crest of a grade', 'Review generated grade profile, crest station and original vehicle-body location during the reversal.'),
        ('turned so as to proceed in the opposite direction', 'Review the complete original forward-reverse-forward path and final travel heading, not a controller request alone.'),
        ('cannot be seen by the driver of any other vehicle approaching from either direction within 500 feet', 'Keep both roadway directions, actual 500-foot road distance, original body rays and pixel review distinct; an analytic centerline ray alone does not establish recognition.')
    ]
    template = {
        'template_id': TEMPLATE, 'law_id': LAW_ID, 'actor': ACTOR, 'status': 'draft',
        'quote': relevance['relevant_laws'][0]['quote'],
        'structure': {
            'law_id': LAW_ID,
            'activation': {'condition': 'A motor vehicle is on a curve or on the approach to or near a grade crest.', 'numeric_conditions': []},
            'obligation': {'type': 'must_not', 'description': 'Turn to proceed in the opposite direction under the stated visibility condition.', 'numeric_conditions': []},
            'exceptions': [],
            'timing': {'description': 'Evaluate location and visibility throughout the observed turn episode.', 'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note in judgments],
        },
        'parameter_refs': [
            {'name': 'turn_to_opposite_direction', 'kind': 'subject_behavior', 'range_or_domain': 'full original heading and signed-motion episode; unknown until captured'},
            {'name': 'curve_or_crest_geometry', 'kind': 'world_setup', 'range_or_domain': 'generated OpenDRIVE curvature and grade readback, including curve and crest alternatives'},
            {'name': 'two_direction_500ft_visibility', 'kind': 'world_setup', 'range_or_domain': 'both original roadway approaches, body rays, pixel review and observer positions at statutory roadway distance'},
        ]}
    put('template.json', template)
    specs = [
        ('curve_geometry', 'structured', 'Generated road station, curvature and original vehicle position during the turn.'),
        ('grade_profile', 'structured', 'Generated road grade, crest station and original vehicle position during the turn.'),
        ('reversal_motion', 'structured', 'Original vehicle-body pose, heading and signed motion through the turn episode.'),
        ('two_direction_visibility', 'structured', 'Both original approaching lanes, roadway-distance stations, nine body rays per direction and independently reviewed pixels.')
    ]
    for index, ((phrase, note), (name, unit, description)) in enumerate(zip(judgments, specs), 1):
        observation = {
            'template_id': TEMPLATE, 'phrase': phrase, 'note': note, 'status': 'draft',
            'observable_requirements': {
                'observables': [{'name': name, 'unit': unit, 'description': description}],
                'context_inputs': [{'name': 'native_map_and_lanes', 'unit': 'structured', 'description': 'Source-hashed generated road and lane readback, including both approaches.'}],
                'sweep_dimensions': [{'name': 'commanded_turn_path', 'unit': 'structured', 'description': 'Authored turn route and physical feasibility range; actual behavior remains measured.'}],
                'landmarks': [],
                'recording_needs': [{'name': name, 'unit': unit, 'description': description},
                                    {'name': 'source_camera_views', 'unit': 'video', 'description': 'Four synchronized original source cameras with frame identities.'}],
                'limitations': ['The authored road and analytic centerline rays are only CPU requests; actual Native body visibility and human recognition require original source review.']
            }}
        put(f'judgment-observables-{index}.json', observation)
    binding = {
        'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'established_contexts': ['Frozen hill_crest/u_turn/other_vehicle is source planning context, not physical proof of the generated grade, actual reversal or visibility.'],
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [
            {'name': 'turn_to_opposite_direction', 'kind': 'subject_behavior', 'range_or_domain': 'original observed body/heading episode, unknown until capture', 'used_by_laws': [LAW_ID]},
            {'name': 'curve_or_crest_geometry', 'kind': 'world_setup', 'range_or_domain': 'generated straight/curved plan-view road and shallow/steep grade readback', 'used_by_laws': [LAW_ID]},
            {'name': 'two_direction_500ft_visibility', 'kind': 'world_setup', 'range_or_domain': 'original body rays and independently reviewed pixels at both roadway approaches', 'used_by_laws': [LAW_ID]},
            {'name': 'commanded_turn_path', 'kind': 'controller', 'range_or_domain': 'authored three-point or stop-before-crest path request; no observed maneuver guaranteed', 'used_by_laws': [LAW_ID]},
            {'name': 'grade_height_m', 'kind': 'world_setup', 'range_or_domain': 'authored 0.8 m or 12 m quadratic crest height at the same station', 'used_by_laws': [LAW_ID]},
            {'name': 'plan_view_curvature_1pm', 'kind': 'world_setup', 'range_or_domain': 'zero on straight crest or reciprocal of authored 300 m circular curve radius', 'used_by_laws': [LAW_ID]},
        ]}
    put('bindings.json', binding)
    common_description = {
        'channels': [
            {'name': name, 'unit': unit, 'sampling_rate_hz': 20,
             'method': 'original Native actor, generated road, body-ray and synchronized camera source join',
             'time_window': '35 seconds / 700 joined frames',
             'reference_frame': 'original Native frame and generated road station',
             'uncertainty': '50 ms sampling; actual source geometry and recognition pending'}
            for name, unit in [('curve_geometry','structured'), ('grade_profile','structured'),
                               ('reversal_motion','structured'), ('two_direction_visibility','structured'),
                               ('source_camera_views','video'), ('native_body_pose_control','structured'),
                               ('camera_frame_join','structured')]],
        'context_inputs': [{'name':'native_map_and_lanes','unit':'structured',
                            'method':'source-hashed generated OpenDRIVE and lane readback'}],
        'limitations':['CPU geometry and requests do not prove original CARLA visibility, physical reversal or legal judgment.']}
    base = {
        'turn_to_opposite_direction': {'kind':'subject_behavior','value':None,'unit':'structured','source':'original Native body and heading'},
        'curve_or_crest_geometry': {'kind':'world_setup','value':{'crest_station_m':200},'unit':'structured','source':'authored road; Native map readback pending'},
        'two_direction_500ft_visibility': {'kind':'world_setup','value':{'observer_road_distance_m':152.4,'directions':['west','east'],'actual_visibility':None},'unit':'structured','source':'statutory distance and authored observer setup; original rays and pixels pending'},
        'commanded_turn_path': {'kind':'controller','value':'three_point_reversal','unit':'structured','source':'authored forward-reverse-forward request'},
        'grade_height_m': {'kind':'world_setup','value':0.8,'unit':'m','source':'authored quadratic grade'},
        'plan_view_curvature_1pm': {'kind':'world_setup','value':0,'unit':'1/m','source':'authored straight plan view'},
    }
    import copy
    cases = [{
        'case_id': ASSIGNMENT+'__baseline', 'target_law_id': None, 'target_type':'baseline',
        'rationale':'Shared source and geometry definition without an expected legal outcome.',
        'variable_assignments':copy.deepcopy(base), 'recording_description':copy.deepcopy(common_description),
        'unresolved_judgment_calls':[]
    }]
    variants = [
        ('probe_01',0.8,0,'crest_grade_pair','grade_height_m','shallow authored crest request'),
        ('probe_02',12,0,'crest_grade_pair','grade_height_m','steep authored crest request'),
        ('probe_03',0.8,1/300,'curve_pair','plan_view_curvature_1pm','curved authored road request'),
    ]
    for suffix, height, curvature, pair, primary, rationale in variants:
        values = copy.deepcopy(base)
        values['grade_height_m']['value'] = height
        values['plan_view_curvature_1pm']['value'] = curvature
        cases.append({
            'case_id':ASSIGNMENT+'__'+suffix, 'target_law_id':LAW_ID, 'target_type':'boundary_probe',
            'rationale':rationale+'; original physical behavior and both-direction visibility remain unresolved.',
            'paired_probe_id':ASSIGNMENT+'__'+pair,
            'deliberate_differences':[primary],
            'probe':{'primary_variable':primary,'comparison_or_standard':'controlled authored geometry contrast; no legal outcome assigned',
                     'target_value_or_branch':height if primary=='grade_height_m' else curvature},
            'variable_assignments':values, 'recording_description':copy.deepcopy(common_description),
            'unresolved_judgment_calls':[phrase for phrase,_ in judgments]
        })
    sweep_specs=[{'sweep_id':f'C104496-407-judgment-{i}', 'target_law_id':LAW_ID,
                  'judgment_refs':[{'phrase':phrase,'note':note}], 'status':'incomplete',
                  'rationale':'A fixed physical observation grid requires original generated-road and full-body visibility feasibility; these diagnostic requests carry no expected label.',
                  'missing_inputs':['Original source feasibility and physical range/resolution for this judgment',
                                    'Complete source-backed selected-case sweep expansion and comparison isolation']}
                 for i,(phrase,note) in enumerate(judgments,1)]
    put('cases.json',{'cell_id':CELL,'actor':ACTOR,'status':'draft','cases':cases,'sweep_specs':sweep_specs})


if __name__ == '__main__':
    author()
