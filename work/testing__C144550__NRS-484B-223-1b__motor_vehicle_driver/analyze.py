"""Saved 223(1)(b) lane change geometry, signal timing and target-lane gap."""
import argparse,hashlib,json
from pathlib import Path
from worker_exchange.native_output import write_result

def source(root,name):
    p=root/name
    if not p.is_file():raise ValueError('Missing required source: '+name)
    return json.loads(p.read_text()) if name.endswith('.json') else [json.loads(s) for s in p.read_text().splitlines() if s.strip()]

def marked_lane_context(road):
    return {'road_id':road['road_id'],'same_direction_lane_ids':road['same_direction_lane_ids'],'marking':road['lane_boundary_marking'],'boundary_y_m':road['lane_boundary_y_m']}

def signal_before_departure(road,rows):
    boundary=road['lane_boundary_y_m']
    first_signal=next((r for r in rows if r['left_blinker']),None)
    first_depart=next((r for r in rows if min(y for _,y in r['ego_body_xy_m'])<boundary),None)
    value={'signal_frames':[r['frame'] for r in rows if r['left_blinker']],'body_departure_frames':[r['frame'] for r in rows if min(y for _,y in r['ego_body_xy_m'])<boundary],'first_signal_observed':first_signal is not None,'first_body_departure_observed':first_depart is not None}
    if first_signal:value['first_signal_frame']=first_signal['frame']
    if first_depart:value['first_body_departure_frame']=first_depart['frame']
    if first_signal and first_depart:value['observed_signal_lead_s']=first_depart['time_s']-first_signal['time_s']
    return value

def target_lane_gap(rows):
    samples=[]
    for r in rows:
        gap=min(x for x,_ in r['ego_body_xy_m'])-max(x for x,_ in r['target_body_xy_m'])
        closing=r['target_speed_mps']-r['ego_speed_mps']
        samples.append({'frame':r['frame'],'time_s':r['time_s'],'signed_longitudinal_surface_gap_m':gap,'closing_speed_mps':closing,'time_to_rear_overlap_s':gap/closing if gap>0 and closing>0 else 0.0,'driver_check_recorded':r['driver_check_recorded']})
    return {'samples':samples,'minimum_signed_surface_gap_m':min(s['signed_longitudinal_surface_gap_m'] for s in samples),'limitation':'Gap and check telemetry are observables; legal ascertainment and safety need local judgment'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    root=Path(a.attempt);case=source(root,'config.json')['case']
    road=source(root,'lane_geometry.json');rows=source(root,'lane_change_history.jsonl')
    hashes={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ('lane_geometry.json','lane_change_history.jsonl')}
    values={'marked_same_direction_lanes':{'method':'marked_lane_context','value':marked_lane_context(road),'sources':{'lane_geometry.json':hashes['lane_geometry.json']}},'indicator_precedes_lane_departure':{'method':'signal_before_departure','value':signal_before_departure(road,rows),'sources':hashes},'target_lane_safety_observations':{'method':'target_lane_gap','value':target_lane_gap(rows),'sources':{'lane_change_history.jsonl':hashes['lane_change_history.jsonl']}}}
    Path(a.output).write_text(json.dumps({'measurements':values,'limitations':['Diagnostic fixture only; actual indicator pixels and driver ascertainment require local review.','No legal safety threshold or verdict.']},indent=2)+'\n')
    traces=source(root,'trace.jsonl');speed=[{'time_s':r['time_s'],'value':r['speed_mps']} for r in traces]
    (root/'speed.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in speed))
    for name,key in [('lane_markings','marked_same_direction_lanes'),('signal_timing','indicator_precedes_lane_departure'),('target_lane_gap','target_lane_safety_observations')]:
        (root/(name+'.jsonl')).write_text(''.join(json.dumps({'time_s':r['time_s'],'value':values[key]['value']})+'\n' for r in traces))
    requested=case['variable_assignments']['approach_speed_mps']['value'];measured=speed[-1]['value']
    result={'case_id':case['case_id'],'measured_values':{'approach_speed_mps':measured},'target_checks':[{'target':'approach_speed_mps','requested':requested,'measured':measured,'method':'last original velocity sample','tolerance':.1,'matched':abs(measured-requested)<=.1,'physical_cause_confirmed':False,'cause_evidence':'trace.jsonl'}],'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,'termination_reason':'diagnostic fixture only','physical_failure_flags':{'lane_change_safety_verified':False},'trace_reference':'trace.jsonl','video_references':['raw.mkv'],'video_frame_map_reference':'video_frames.jsonl','recording_description':case['recording_description'],'recording_evidence':[{'name':n,'unit':u,'reference':f} for n,u,f in [('kin.speed','m/s','speed.jsonl'),('lane_markings','structured','lane_markings.jsonl'),('signal_timing','structured','signal_timing.jsonl'),('target_lane_gap','structured','target_lane_gap.jsonl')]],'realized_observables':{}}
    write_result(root,result)
if __name__=='__main__':main()
