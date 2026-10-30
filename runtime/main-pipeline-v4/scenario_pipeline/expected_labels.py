"""Evidence-backed scenario expectations, independent of formalization checking."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from batch_pipeline.store import atomic


def load(path):
    return json.loads(Path(path).read_text())


def rows(path):
    with Path(path).open() as stream:
        return [json.loads(line) for line in stream]


def first_scene(path):
    with Path(path).open() as stream:
        text=stream.read(2000000)
    return json.JSONDecoder().raw_decode(text[text.index('{',text.index('[')):])[0]


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def expectation(case, attempt, review, context):
    ident=case['case_id'];law=case['target_law_id'];trace=rows(attempt/'trace.jsonl')
    result=load(attempt/'result.json');scene=first_scene(attempt/'traffic_spec/trace.json')
    record={'case_id':ident,'target_law_id':law,'expected_label':None,'intended_outcome':None,
            'label_scope':'full_delivered_trace_where_target_rule_applies',
            'scene_assumptions':context,'evidence':{},'missing_evidence':[],'intention_matched':False,
            'trace_reference':str(attempt/'traffic_spec/trace.json'),
            'trace_sha256':sha(attempt/'traffic_spec/trace.json'),
            'definition_sha256':hashlib.sha256(json.dumps(case,sort_keys=True).encode()).hexdigest(),
            'full_recording_window_s':[trace[0]['time_s'],trace[-1]['time_s']],
            'judgment_sweep':case.get('target_type')=='judgment_sweep' or 'appropriate-signal-' in ident}
    if record['judgment_sweep']:
        record['label_exception']='Judgment sweep: no assumed appropriateness threshold';return record
    if not review.get('trace_integrity_confirmed') or not result.get('maneuver_completed'):
        record['missing_evidence'].append('Complete joined capture and maneuver required');return record
    if law in ('NRS-484B-600-1c','NRS-484B-600-1e'):
        speed=review['speed_evaluation'];record['expected_label']=speed['expected_speed_rule_label'] if speed['expected_speed_rule_label']!='unknown' else None
        record['intended_outcome']=speed['intended_numeric_label'];record['evidence']={'measurement':speed}
        if law=='NRS-484B-600-1c':
            if not speed.get('physical_control_evidence'):
                record['missing_evidence'].append(speed.get('physical_control_error','Verified native sign approach and passage required'))
            record['evidence']['physical_control_evidence']=speed.get('physical_control_evidence')
            active=set(speed['applicable_frames']);entry=next((i for i,r in enumerate(trace) if r['frame'] in active),None)
            record['evidence']['recorded_transition_into_posted_portion']=entry is not None and entry>0
            if entry is None or entry==0:record['missing_evidence'].append('Required recorded passage into the posted portion is missing')
            record['evidence']['posted_portion_entry_bracket_s']=[trace[max(0,entry-1)]['time_s'],trace[entry]['time_s']] if entry is not None else None
            governed={rid for d in scene['devices'] if d['kind']=='traffic_signal' for rid in d.get('governs',[])}
            regions=[s for s in scene['structures'] if s['id'] in governed]
            right=max((p[0] for s in regions for p in s['boundary']),default=-math.inf)
            subject=next(u for u in scene['users'] if u['track']==scene['subject']);extent=math.hypot(*subject['kin']['extent'][:2])
            clearance=min(r['position']['x'] for r in trace)-extent-right
            record['evidence']['nearby_signal_region_clearance_lower_bound_m']=clearance
            record['evidence']['no_signal_region_overlap']=clearance>0
            if clearance<=0:record['missing_evidence'].append('Traffic-light interference requires further geometry checks')
    elif '-lanes-' in ident:
        cfg=load(attempt/'config.json');n=cfg['lane_count'];record['evidence']={'same_direction_lane_count':n,'lane_directions':[s['lane'].get('direction') for s in scene['structures'] if s['kind']=='lane']}
        record['intended_outcome']='not_applicable' if n<2 else 'compliant'
        if n<2 and result['measured_values'].get('straight_travel_completion_observed'):
            record['expected_label']='not_applicable'
        elif n>=2:
            indicators=rows(attempt/'ego_turn_indicator.jsonl');onset=review.get('maneuver_onset_bracket_s');states=[r['value'].get('reported_device_state',r['value'].get('state')) for r in indicators if onset and onset[0]-1<=r['time_s']<=onset[1]]
            record['evidence']['indicator_before_departure']=states
            if not states or not context.get('fixed_non_swept_conditions'):record['missing_evidence'].append('Fixed signaling/safety conditions and observed indicator required')
            else:
                inventory=rows(attempt/'target_lane_user_trajectory.jsonl')
                clear=bool(len(inventory)==len(trace) and all(abs(a['time_s']-b['time_s'])<1e-6 and not a['value']['users'] for a,b in zip(inventory,trace)))
                record['evidence']['complete_recorded_destination_user_inventory_empty']=clear
                if not clear:record['missing_evidence'].append('Empty destination-user inventory not verified throughout trace')
                else:record['expected_label']='compliant' if all(s=='left' for s in states) else 'non_compliant'
    elif law=='NRS-484A-450-2':
        samples=rows(attempt/'stopping_and_entry_evidence.jsonl');moving=[r for r in samples if r['value']['phase']!='approach' or r['value']['route_station_m']>1]
        held=[r for r in moving if r['value']['phase']=='hold'];eps=1e-5
        ref=context.get('stopping_reference',{}).get('physical_reference',{});line=ref.get('endpoints_carla_m')
        clearance={}
        if line and (attempt/'ego_footprint.jsonl').exists():
            footprints=rows(attempt/'ego_footprint.jsonl');dx=line[1][0]-line[0][0];dy=line[1][1]-line[0][1];length=math.hypot(dx,dy);nx=dy/length;ny=-dx/length
            initial=footprints[0]['value']['vertices_m'][0]
            if (initial[0]-line[0][0])*nx+(initial[1]-line[0][1])*ny<0:nx=-nx;ny=-ny
            clearance={r['time_s']:min((v[0]-line[0][0])*nx+(v[1]-line[0][1])*ny for v in r['value']['vertices_m']) for r in footprints}
        stop=[r for r in held if r['value']['measured_speed_mps']<=eps and clearance.get(r['time_s'],-math.inf)>0]
        crossed=[r for r in moving if clearance.get(r['time_s'],math.inf)<0]
        record['intended_outcome']='non_compliant' if case.get('target_type')=='violating_attempt' or 'violating' in ident else 'compliant'
        record['evidence']={'stopping_reference':context.get('stopping_reference'),'stationary_resolution_mps':eps,'stationary_resolution_note':'Numerical observation resolution, not a permitted rolling-stop speed','stop_samples':len(stop),'minimum_stop_front_clearance_m':min((clearance[r['time_s']] for r in stop),default=None),'crossing_observed':bool(crossed),'boundary_method':'Signed perpendicular front/body distance to native recorded stop-line endpoints'}
        if context.get('stopping_reference'):
            from shapely.geometry import Polygon
            native=load(attempt/'context.json')['ordered_stopping_references']['native_marked_crosswalk_vertices_m']
            groups=[];group=[]
            for v in native:
                group.append(v[:2])
                if len(group)>2 and group[0]==group[-1]:groups.append(group);group=[]
            approach=Polygon([line[0],line[1],[line[1][0]+nx*ref['route_station_m'],line[1][1]+ny*ref['route_station_m']],[line[0][0]+nx*ref['route_station_m'],line[0][1]+ny*ref['route_station_m']]])
            intersections=[i for i,g in enumerate(groups) if Polygon(g).intersects(approach)]
            record['evidence']['native_marked_crosswalks_on_approach']=intersections
            if intersections:record['missing_evidence'].append('Native crosswalk contradicts declared stop-line branch');record['expected_label']=None;return record
        if not context.get('stopping_reference'):record['missing_evidence'].append('Applicable stopping reference unresolved')
        elif crossed:record['expected_label']='compliant' if stop and stop[0]['time_s']<crossed[0]['time_s'] else 'non_compliant'
        else:record['missing_evidence'].append('No observed passage of stopping reference')
    elif law=='NRS-484B-307-6a':
        body=rows(attempt/'footprint_boundary_relationships.jsonl');signals=rows(attempt/'governing_signal_indication.jsonl');bytime={r['time_s']:r['value']['state'] for r in signals}
        entries=[r for i,r in enumerate(body) if i and r['value']['relations']['first_overlap'] and not body[i-1]['value']['relations']['first_overlap']]
        states=[bytime.get(r['time_s']) for r in entries];record['intended_outcome']='non_compliant' if case.get('target_type')=='violating_attempt' or 'violating' in ident else 'compliant'
        record['evidence']={'entry_convention':'First recorded front/body overlap of native intersection surface; original time brackets retained','entry_times_s':[r['time_s'] for r in entries],'governing_signal_states':states}
        if not states or any(s is None for s in states):record['missing_evidence'].append('Observed intersection entry with joined governing indication required')
        else:record['expected_label']='non_compliant' if 'Red' in states else 'compliant'
    elif law in ('NRS-484B-400-2a','NRS-484B-400-2b'):
        points=rows(attempt/'ego_trajectory.jsonl');approach=[r['value'] for r in points if -30<=r['value']['position_authored_m']['x']<=-14];exit_points=[r['value'] for r in points if 14<=r['value']['position_authored_m']['y']<=30]
        record['intended_outcome']='non_compliant' if case.get('target_type')=='violating_attempt' or 'violating' in ident else 'compliant'
        if law.endswith('2a'):
            offsets=[r['signed_approach_centerline_offset_m'] for r in approach];okay=bool(offsets) and all(-3.5<x<0 for x in offsets)
        else:
            offsets=[r['signed_entered_centerline_offset_m'] for r in exit_points];okay=bool(offsets) and all(x>0 for x in offsets)
        record['evidence']={'centerline_offsets_m':{'minimum':min(offsets,default=None),'maximum':max(offsets,default=None)},'lane_direction_source':'Delivered structures[].lane.direction and authored centerlines','measurement':'Approach in inner right-half lane before intersection; exit to right of entered highway centerline'}
        if offsets:record['expected_label']='compliant' if okay else 'non_compliant'
        else:record['missing_evidence'].append('Missing approach/exit position evidence')
    elif law=='NRS-484B-413-2':
        threshold=100 if '-100-' in ident else 300
        lead=review.get('api_signal_lead')
        if lead and lead.get('value') is not None:distance=lead['value']/.3048;interval=lead.get('sampling_distance_interval_m');interval=[x/.3048 for x in interval] if interval else None
        else:
            distance=result['measured_values'].get('continuous_indicator_distance_before_numerical_onset_ft');interval=result['measured_values'].get('continuous_indicator_distance_bracket_ft')
        record['intended_outcome']='non_compliant' if ident.endswith('-below') else 'compliant'
        record['evidence']={'minimum_signal_distance_ft':threshold,'measured_api_continuous_distance_ft':distance,'sampling_interval_ft':interval,'district':context.get('district'),'event_definition':review.get('maneuver_onset_bracket_s'),'distance_convention':'Compare the recorded scalar to the minimum under the declared sampled maneuver-event convention; preserve timing/distance brackets separately, including brackets that straddle the threshold', 'signal_source':'Original indicator states and recorded trajectory; rendered flashing evidence separately linked'}
        if not context.get('district') or distance is None:record['missing_evidence'].append('Declared district and measured continuous signal distance required')
        else:record['expected_label']='compliant' if distance>=threshold else 'non_compliant'
    elif law in ('NRS-484B-113-2','NRS-484B-220-1','NRS-484B-227-1','NRS-484B-250-1','NRS-484B-250-2','NRS-484B-250-4'):
        from demo_rule_evidence import evaluate
        try:
            record.update(evaluate(case, attempt, trace, context))
        except (ValueError, KeyError, OSError) as exc:
            record['missing_evidence'].append(str(exc))
    declared=case.get('expected_label_specification',{}).get('intended_outcome')
    if declared in ('compliant','non_compliant','not_applicable'):record['intended_outcome']=declared
    if record['missing_evidence']:record['expected_label']=None
    record['intention_matched']=record['expected_label']==record['intended_outcome'] if record['expected_label'] else False
    return record


def scene_context(case,attempt, *, legacy=True):
    ident=case['case_id'];ctx={'provenance':'Explicit synthetic scenario assumptions authorized in repair plan; native observations remain separately preserved' if legacy else 'Explicit frozen case/construction assumptions; no context inferred from case names or controller intentions'}
    if legacy and '-413-2-' in ident:ctx['district']='business_or_residential' if '-100-' in ident else 'other_area'
    if legacy and '-lanes-' in ident:
        ctx['fixed_non_swept_conditions']={'markings':'Clearly marked lanes are an explicit synthetic applicability assumption; native lane topology is observed, while painted markings are not established in the saved rendering','appropriate_signal':'Correct left indicator, continuously enabled well before movement; fixed test assumption','safety':'Empty destination lane and road, complete simulator participant inventory; driver ascertains this authored clear condition (scenario assumption, not inferred mental state)'}
    if legacy and '-450-2-' in ident:
        original=load(attempt/'context.json');ref=original['ordered_stopping_references']['physical_candidate']
        ctx['stopping_reference']={'branch':'marked_stop_line','physical_reference':ref,'crosswalk_absent_on_tested_approach':'Authored synthetic applicability fact; native marked-crosswalk inventory checked separately','unmarked_crosswalk_absent':'Explicit synthetic test assumption, not inferred from lack of map annotation'}
    if legacy and '-307-6a-' in ident:ctx['intersection_entry_convention']='First body overlap of native intersection surface'
    declarations=[case.get('scene_assumptions',{}),case.get('expected_label_specification',{}).get('scene_assumptions',{})]
    config_path=attempt/'config.json'
    if config_path.exists():
        configuration=load(config_path)
        declarations.append(configuration.get('scene_assumptions',{}))
        if not legacy:declarations.append(configuration.get('authored_test_context',{}))
    for declaration in declarations:
        if isinstance(declaration,list) and all(isinstance(v,str) for v in declaration):
            ctx.setdefault('declarations',[]).extend(v for v in declaration if v not in ctx.get('declarations',[]))
            continue
        if not isinstance(declaration,dict):raise ValueError('Scene assumptions must be an explicit object or string declarations')
        for name,value in declaration.items():
            if name in ctx and name!='provenance' and ctx[name]!=value:raise ValueError('Conflicting authored scene context: '+name)
            ctx[name]=value
    if case.get('deterministic_branch'):ctx['deterministic_branch']=case['deterministic_branch']
    return ctx



def resolve_declared_context(definition, context, attempt):
    """Resolve declared applicability while preserving consumed requests."""
    assignments=definition.get('variable_assignments',{})
    definition.setdefault('source_variable_assignments',deepcopy(assignments))
    definition['variable_assignments_semantics']='Controller targets and subject observation requests are preserved; required applicability fields below are resolved with explicit provenance.'
    if context.get('district'):
        for name in ('approach_location_and_land_use','surrounding_land_use'):
            if name in assignments and isinstance(assignments[name].get('value'),dict):
                assignments[name]['value']['legal_region_classification']=context['district']
                assignments[name]['value']['classification_basis']='Declared synthetic test assumption; native geographic alignment and land-use observations remain unavailable'
    if context.get('stopping_reference'):
        if 'near_side_crosswalk' in assignments:
            assignments['near_side_crosswalk']['value'].update(presence=False,status='declared_absent_for_synthetic_test',provenance=context['stopping_reference']['unmarked_crosswalk_absent'])
        if 'stop_line' in assignments:
            assignments['stop_line']['value'].update(presence=True,clearly_marked=True,geometry=context['stopping_reference']['physical_reference'],status='native_reference_selected',provenance='Native OpenDRIVE StopLine object and recorded endpoints; declared no-crosswalk branch')
    if context.get('fixed_non_swept_conditions') and 'lane_markings' in assignments:
        assignments['lane_markings']['value'].update(clearly_marked_interpretation='fixed_synthetic_assumption',status='declared_applicability_with_observed_native_topology',provenance=context['fixed_non_swept_conditions']['markings'])
    if (attempt/'rendered_indicator_review.json').exists() and 'indicator_observation_channel' in assignments:
        assignments['indicator_observation_channel']['value'].update(reported_device_state_channel='ego_turn_indicator.jsonl',externally_observed_lamp_channel='rendered_indicator_review.json',provenance='Original API state and separately verified saved lamp images; not a driver perception claim')


def apply(output, validator=None):
    index=load(output/'delivery_index.json');records=[]
    for cell in index['cells']:
        for item in cell['cases']:
            attempt=Path(item['execution']);source=output.parent/item.get('definition_run_id',cell.get('run_id',index['run_id']))/'cells'/cell['cell_id']/'motor_vehicle_driver/cases.json'
            definition=load(item['definition_file']) if item.get('definition_file') else next(c for c in load(source)['cases'] if c['case_id']==item['case_id'])
            context=scene_context(definition,attempt)
            from authored_context import inject
            decoder=validator or load(attempt/'traffic_spec/adapter_report.json').get('decoder_validation',{}).get('executable')
            if not decoder:
                raise ValueError('Provide the configured Lean decoder validator; no campaign-specific executable is assumed')
            inject(attempt,context,Path(decoder))
            definition=deepcopy(definition);resolve_declared_context(definition,context,attempt)
            from authored_context import assumptions
            definition['expected_label_specification']={'core_assumptions':assumptions(context),'scope':'Recorded scenario under explicit synthetic context','scene_assumptions':context,'approved_targets_unchanged':True}
            definition['source_definition_preserved']=str(source)
            path=attempt/'expected_label_case_definition.json';atomic(path,definition);item['definition_file']=str(path)
            record=expectation(definition,attempt,load(attempt/'measured_review.json'),context)
            definition['expected_label_specification']['intended_outcome']=record['intended_outcome']
            definition['expected_label_specification']['observed_expected_label']=record['expected_label']
            definition['expected_label_specification']['evidence_reference']=str(attempt/'expected_label.json')
            definition['source_unresolved_inputs']=definition.pop('missing_inputs',definition.get('source_unresolved_inputs',[]))
            definition['execution_readiness']='judgment_sweep_recorded' if record['judgment_sweep'] else 'validated_recording' if record['intention_matched'] else 'repair_required'
            atomic(path,definition);record['definition_sha256']=sha(path)
            atomic(attempt/'expected_label.json',record);atomic(attempt/'traffic_spec/expected_label_context.json',{'scene_assumptions':context,'expected_label_reference':str(attempt/'expected_label.json'),'trace_sha256':record['trace_sha256']})
            item['expected_label']=record['expected_label'];item['expected_label_record']=str(attempt/'expected_label.json');item['expected_label_status']='judgment_sweep' if record['judgment_sweep'] else 'accepted' if record['intention_matched'] else 'needs_repair'
            records.append(record)
    index.pop('legal_compliance_evaluated',None)
    index['status']='expected_labels_complete' if all(r['judgment_sweep'] or r['intention_matched'] for r in records) else 'expected_label_repairs_in_progress'
    atomic(output/'delivery_index.json',index)
    audit={'status':'complete' if all(r['judgment_sweep'] or r['intention_matched'] for r in records) else 'repairs_required','counts':dict(Counter(r['expected_label'] or ('judgment_sweep' if r['judgment_sweep'] else 'missing_evidence') for r in records)),'cases':records,'repairs_required':[r['case_id'] for r in records if not r['judgment_sweep'] and not r['intention_matched']]}
    atomic(output/'expected_label_audit.json',audit);print(json.dumps({k:v for k,v in audit.items() if k!='cases'},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--validator',type=Path,required=True);args=p.parse_args();apply(args.output,args.validator)
