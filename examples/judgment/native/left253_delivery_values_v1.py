"""Measured delivery channels and physical completion, without legal judgments."""
import json,math
from pathlib import Path

def values(row,event,distance):
 s=row['states'];ego=s['ego'];frame=row['frame'];time=row['time_s']
 return {'ego_speed':ego['speed_mps'],'participant_native_state':s,'intersection_occupancy':row['occupancy'],'native_actor_inventory':row['native_actor_inventory'],
 'queried_signal_history':{'method':'vehicle signal lamp/device','actual_native_bits':ego['light_state_native'],'indication':'left queried bit; visible lamp independently audited from signal.mkv','photometric_illumination':'not inferred from bit'},
 'signal_path_integration':distance,'participant_interaction_history':{'states':s,'occupancy':row['occupancy'],'actual_controls':{k:v['applied_control'] for k,v in s.items()},'engineering_phase':row['engineering_phase'],'requested_controls':row['control_requests'],'contacts':row['contacts']},
 'weather_and_devices':{'actual_weather':event['world']['weather'],'native_inventory':row['governing_native_inventory']},
 'original_camera_graph_body_Core_joins':{'native_frame':frame,'original_time_s':time,'expected_core_time_ms':round(time*1000),'actual_Core_join':'Pending independent saved-only conversion and audit; never asserted from a native request','original_capture_frame':event['original_frame'],'native_body_actor_ids':[v['actor_id'] for v in s.values()],'cameras':row['camera_metadata']},
 'opposing_boundary_relative_position':row['occupancy']['initial_opposing']['opposing_front_signed_distance_m'],'opposing_approach_speed':s['initial_opposing']['speed_mps'],'opposing_stream_count':len(s)-2}

def finish(out,cfg,rows,report,error,distance_rows):
 out=Path(out);duration=cfg['duration_s'];count=cfg['maximum_frames'];inside=next((r for r in rows if r['occupancy']['ego']['full_body_inside']),None);roles=set(rows[0]['states']) if rows else set()
 cleared={role:any(max(v[1 if role=='ego' else 0] for v in r['states'][role]['body_vertices_native_m'])< -7 for r in rows) for role in roles}
 final=[r for r in rows if r['time_s']>duration-3]
 mask=json.loads((out/'signal-method.json').read_text())['native_left_indicator_bit'] if rows else None;continuous=bool(rows) and all(r['states']['ego']['light_state_native']&mask for r in rows)
 before_change=None
 if rows:
  heading=rows[0]['states']['ego']['yaw_rad']
  for i,r in enumerate(rows):
   delta=abs(math.degrees(math.atan2(math.sin(r['states']['ego']['yaw_rad']-heading),math.cos(r['states']['ego']['yaw_rad']-heading))))
   if delta>.1:before_change=distance_rows[max(0,i-1)];break
 expected_roles={'ego','initial_opposing'}|{'further_opposing_'+str(i+1) for i in range(cfg['further_count'])}
 identities_complete=roles==expected_roles and all(set(r['states'])==roles and len({s['actor_id'] for s in r['states'].values()})==len(roles) and {s['actor_id'] for s in r['states'].values()}=={a['id'] for a in r['native_actor_inventory'] if a['type_id'].startswith('vehicle.')} for r in rows)
 gates={'complete_participant_identity_inventory':identities_complete,'complete_original_contract':len(rows)==count and error is None,'actual_ego_within_intersection':inside is not None,'actual_turn_completed':report['ego_turn_completed'],'all_participant_crossings_cleared':bool(cleared) and all(cleared.values()),'all_native_bodies_on_authored_pavement':bool(rows) and all(all(r['body_inside_authored_pavement'].values()) for r in rows),'no_contacts':not report['contacts'],'at_least_three_seconds_final_stopped_observation':len(final)>=59 and all(s['speed_mps']<.1 for r in final for s in r['states'].values()),'queried_indicator_continuous':continuous,'recorded_advance_signal_engineering_margin':before_change is not None and before_change>=36.576}
 checks=[{'target':k,'requested':True,'measured':{'observed':v},'method':'Complete original same-frame native body/control/trajectory history; geometric, physical and engineering evidence only','tolerance':'No missing mandatory samples or incomplete physical outcomes','matched':v,'physical_cause_confirmed':bool(rows),'cause_evidence':['native-motion.jsonl','video_frames.jsonl','capture/evidence.jsonl']} for k,v in gates.items()]
 if cfg['comparison']=='initial_opposing_position':
  measured=None if inside is None else inside['occupancy']['initial_opposing']['opposing_front_signed_distance_m'];matched=measured is not None and abs(measured-cfg['initial_position_proposal_m'])<=1.
  if cfg['initial_position_proposal_m']<0:matched=matched and inside['occupancy']['initial_opposing']['full_body_inside']
  gates['prospective_position_realized']=matched
  checks.append({'target':'opposing_front_at_first_full_ego_inside','requested':cfg['initial_position_proposal_m'],'measured':{'distance_m':measured,'opponent_full_body_inside':None if inside is None else inside['occupancy']['initial_opposing']['full_body_inside']},'method':'All eight native body vertices; minimum native x minus roadway entry boundary x=7m, at first original frame of unambiguous full ego body containment','tolerance':{'engineering_m':1.,'justification':'50ms sampling (nominal opposing motion0.3m/tick), native body/pose float precision, three16m-separated physical settings; not a legal hazard boundary'},'matched':matched,'physical_cause_confirmed':inside is not None,'cause_evidence':['native-motion.jsonl']})
 realized={}
 for axis in cfg['case'].get('sweep_measurements',[]):
  name=axis['observable'];window=cfg['summary_windows'][name]
  if window=='first_ego_full_body_inside':chosen=[] if inside is None else [inside]
  else:chosen=[r for r in rows if window[0]-1e-6<=r['time_s']<=window[1]+1e-6]
  if not chosen:continue
  samples=[]
  for r in chosen:
   samples.append(r['occupancy']['initial_opposing']['opposing_front_signed_distance_m'] if name=='opposing_boundary_relative_position' else r['states']['initial_opposing']['speed_mps'] if name=='opposing_approach_speed' else len(r['states'])-2 if name=='opposing_stream_count' else None)
  assert all(isinstance(v,(int,float)) for v in samples),'Unsupported selected physical measurement'
  definition=axis['measurement'];stat=definition['statistic'];value={'first':lambda x:x[0],'last':lambda x:x[-1],'mean':lambda x:sum(x)/len(x),'min':min,'max':max}[stat](samples)
  realized[name]={'value':value,'unit':axis['unit'],**definition,'sample_window_s':[chosen[0]['time_s'],chosen[-1]['time_s']],'reference':'channels/'+name+'.jsonl'}
 complete=all(gates.values())
 result={'status':'draft','cell_id':'C329654','actor':'motor_vehicle_driver','case_id':cfg['case_id'],'input_revision':cfg['input_revision'],'primary_video_reference':'overview.mkv','setup_confirmed':bool(rows),'behavior_attempted':bool(rows) and any(r['states']['ego']['speed_mps']>0 for r in rows),'maneuver_completed':complete,'termination_reason':'complete_recorded_left_turn_and_all_opposing_outcomes' if complete else 'incomplete_physical_evidence','physical_failure_flags':{'collision':bool(report['contacts']),'roadway_departure':not gates['all_native_bodies_on_authored_pavement']},'target_checks':checks,'measured_values':{'frames':len(rows),'duration_s':rows[-1]['time_s'] if rows else 0,'first_full_ego_inside_time_s':None if inside is None else inside['time_s'],'all_participant_clearance':cleared,'advance_signal_distance_lower_m':before_change},'trace_reference':'trace.jsonl','video_references':['overview.mkv','signal.mkv'],'video_frame_map_reference':'video_frames.jsonl','recording_description':cfg['recording_description'],'recording_evidence':[{'name':c['name'],'unit':c['unit'],'reference':'channels/'+c['name']+'.jsonl'} for c in cfg['recording_description']['channels']]+[{'name':c['name'],'unit':c['unit'],'reference':'context.json'} for c in cfg['recording_description']['context_inputs']],'realized_observables':realized,'recording_complete':len(rows)==count and error is None,'requested_variable_assignments':{k:v for k,v in cfg['variable_assignments'].items() if v['kind'] in ('world_setup','controller')},'authored_context':cfg['authored_test_context'],'error':error,'restoration':{'restored':report['restored']},'limitations':cfg['recording_description']['limitations'],'judgments_unresolved':['immediate hazard','having so yielded','lawful progression','reasonable safety'],'source_photometry_and_Core_acceptance':'Mandatory separate saved-only audit; native worker success does not establish acceptance'}
 with (out/'result.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
 return complete
