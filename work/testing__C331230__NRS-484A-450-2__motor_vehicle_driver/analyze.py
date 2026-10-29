"""Near-side crosswalk stopping measurements from saved original geometry."""
import argparse,hashlib,json
from pathlib import Path
from worker_exchange.native_output import write_result

def source(root,name):
    p=root/name
    if not p.is_file():raise ValueError('Missing required source: '+name)
    return json.loads(p.read_text()) if name.endswith('.json') else [json.loads(s) for s in p.read_text().splitlines() if s.strip()]

def stop_sign_context(control):
    return {'sign_id':control['stop_sign_id'],'governing_approach_road_id':control['governing_approach_road_id'],'selected_branch':control['selected_branch'],'native_sign_inventory_required':True}

def crosswalk_reference(control):
    return {'crosswalk_upstream_x_m':control['crosswalk_upstream_x_m'],'crosswalk_downstream_x_m':control['crosswalk_downstream_x_m'],'marked_stopline_present':control['marked_stopline_present'],'near_side_of_intersection':control['near_side_of_intersection'],'physical_tiles_required':True}

def stopping_sequence(control,rows):
    upstream=control['crosswalk_upstream_x_m']
    samples=[]
    for r in rows:
        front=max(x for x,_ in r['ego_body_xy_m'])
        samples.append({'frame':r['frame'],'time_s':r['time_s'],'speed_mps':r['ego_speed_mps'],'body_front_x_m':front,'front_to_crosswalk_upstream_m':upstream-front,'before_crosswalk':front<upstream,'before_intersection':front<control['intersection_upstream_x_m']})
    return {'samples':samples,'minimum_observed_speed_mps':min(r['speed_mps'] for r in samples),'minimum_speed_frame':min(samples,key=lambda r:r['speed_mps'])['frame'],'crosswalk_entry_frames':[r['frame'] for r in samples if not r['before_crosswalk']],'legal_stop_epsilon_applied':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    root=Path(a.attempt);case=source(root,'config.json')['case']
    control=source(root,'stop_control.json');rows=source(root,'stop_history.jsonl')
    hashes={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ('stop_control.json','stop_history.jsonl')}
    values={'governing_stop_sign':{'method':'stop_sign_context','value':stop_sign_context(control),'sources':{'stop_control.json':hashes['stop_control.json']}},'near_side_crosswalk_reference':{'method':'crosswalk_reference','value':crosswalk_reference(control),'sources':{'stop_control.json':hashes['stop_control.json']}},'observed_stop_before_crosswalk':{'method':'stopping_sequence','value':stopping_sequence(control,rows),'sources':hashes}}
    Path(a.output).write_text(json.dumps({'measurements':values,'limitations':['Diagnostic fixture only; actual original-frame sign and crosswalk pixels require GPU review.','Minimum sampled speed does not establish a full legal stop; no epsilon or compliance verdict.']},indent=2)+'\n')
    traces=source(root,'trace.jsonl');speed=[{'time_s':r['time_s'],'value':r['speed_mps']} for r in traces]
    (root/'speed.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in speed))
    for name,key in [('governing_sign','governing_stop_sign'),('crosswalk_geometry','near_side_crosswalk_reference'),('stopping_motion','observed_stop_before_crosswalk')]:
        (root/(name+'.jsonl')).write_text(''.join(json.dumps({'time_s':r['time_s'],'value':values[key]['value']})+'\n' for r in traces))
    requested=case['variable_assignments']['approach_speed_mps']['value'];measured=speed[-1]['value']
    result={'case_id':case['case_id'],'measured_values':{'approach_speed_mps':measured},'target_checks':[{'target':'approach_speed_mps','requested':requested,'measured':measured,'method':'last original velocity sample','tolerance':.1,'matched':abs(measured-requested)<=.1,'physical_cause_confirmed':False,'cause_evidence':'trace.jsonl'}],'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,'termination_reason':'diagnostic fixture only','physical_failure_flags':{'full_stop_verified':False},'trace_reference':'trace.jsonl','video_references':['raw.mkv'],'video_frame_map_reference':'video_frames.jsonl','recording_description':case['recording_description'],'recording_evidence':[{'name':n,'unit':u,'reference':f} for n,u,f in [('kin.speed','m/s','speed.jsonl'),('governing_sign','structured','governing_sign.jsonl'),('crosswalk_geometry','structured','crosswalk_geometry.jsonl'),('stopping_motion','structured','stopping_motion.jsonl')]],'realized_observables':{}}
    write_result(root,result)
if __name__=='__main__':main()
