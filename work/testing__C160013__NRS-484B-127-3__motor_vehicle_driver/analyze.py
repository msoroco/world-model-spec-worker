"""Full-body caravan gaps and entrant occupancy from saved original samples."""
import argparse,hashlib,json
from pathlib import Path
from worker_exchange.native_output import write_result

def source(root,name):
    p=root/name
    if not p.is_file():raise ValueError('Missing required source: '+name)
    return json.loads(p.read_text()) if name.endswith('.json') else [json.loads(s) for s in p.read_text().splitlines() if s.strip()]

def caravan_context(context):
    return {k:context[k] for k in ('highway_id','outside_business_district_basis','caravan_purpose','vehicle_roles')}

def intervehicle_gap(rows):
    samples=[]
    for r in rows:
        lead_rear=min(x for x,_ in r['lead_body_xy_m'])
        follow_front=max(x for x,_ in r['follow_body_xy_m'])
        samples.append({'frame':r['frame'],'time_s':r['time_s'],'signed_surface_gap_m':lead_rear-follow_front,'lead_speed_mps':r['lead_speed_mps'],'follow_speed_mps':r['follow_speed_mps']})
    return {'samples':samples,'minimum_signed_surface_gap_m':min(v['signed_surface_gap_m'] for v in samples),'sampling_note':'Original full-body longitudinal surface gap throughout sampled interval'}

def entrant_occupancy(rows):
    values=[]
    for r in rows:
        entrance=min(x for x,_ in r['entrant_body_xy_m'])
        exit=max(x for x,_ in r['entrant_body_xy_m'])
        follow_front=max(x for x,_ in r['follow_body_xy_m'])
        lead_rear=min(x for x,_ in r['lead_body_xy_m'])
        lateral=min(y for _,y in r['entrant_body_xy_m'])
        inside=lateral<4.0 and entrance>follow_front and exit<lead_rear
        values.append({'frame':r['frame'],'time_s':r['time_s'],'between_caravan_bodies':entrance>follow_front and exit<lead_rear,'in_caravan_lane':lateral<4.0,'occupies_gap':inside,'rear_clearance_m':entrance-follow_front,'front_clearance_m':lead_rear-exit,'entrant_speed_mps':r['entrant_speed_mps']})
    return {'samples':values,'occupancy_frames':[v['frame'] for v in values if v['occupies_gap']],'danger_standard_applied':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    root=Path(a.attempt);case=source(root,'config.json')['case']
    context=source(root,'caravan_context.json');rows=source(root,'caravan_history.jsonl')
    hashes={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ('caravan_context.json','caravan_history.jsonl')}
    values={'caravan_outside_district_context':{'method':'caravan_context','value':caravan_context(context),'sources':{'caravan_context.json':hashes['caravan_context.json']}},'caravan_full_body_spacing':{'method':'intervehicle_gap','value':intervehicle_gap(rows),'sources':{'caravan_history.jsonl':hashes['caravan_history.jsonl']}},'entrant_gap_occupation':{'method':'entrant_occupancy','value':entrant_occupancy(rows),'sources':{'caravan_history.jsonl':hashes['caravan_history.jsonl']}}}
    Path(a.output).write_text(json.dumps({'measurements':values,'limitations':['Diagnostic fixture only; Native caravan purpose and outside-business-district premise require local confirmation.','Gap occupation does not resolve without-danger legal judgment.']},indent=2)+'\n')
    traces=source(root,'trace.jsonl');speed=[{'time_s':r['time_s'],'value':r['speed_mps']} for r in traces]
    (root/'speed.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in speed))
    for name,key in [('caravan_roles','caravan_outside_district_context'),('surface_gap','caravan_full_body_spacing'),('entrant_trajectory','entrant_gap_occupation')]:
        (root/(name+'.jsonl')).write_text(''.join(json.dumps({'time_s':r['time_s'],'value':values[key]['value']})+'\n' for r in traces))
    requested=case['variable_assignments']['approach_speed_mps']['value'];measured=speed[-1]['value']
    result={'case_id':case['case_id'],'measured_values':{'approach_speed_mps':measured},'target_checks':[{'target':'approach_speed_mps','requested':requested,'measured':measured,'method':'last original velocity sample','tolerance':.1,'matched':abs(measured-requested)<=.1,'physical_cause_confirmed':False,'cause_evidence':'trace.jsonl'}],'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,'termination_reason':'diagnostic fixture only','physical_failure_flags':{'without_danger_verified':False},'trace_reference':'trace.jsonl','video_references':['raw.mkv'],'video_frame_map_reference':'video_frames.jsonl','recording_description':case['recording_description'],'recording_evidence':[{'name':n,'unit':u,'reference':f} for n,u,f in [('kin.speed','m/s','speed.jsonl'),('caravan_roles','structured','caravan_roles.jsonl'),('surface_gap','structured','surface_gap.jsonl'),('entrant_trajectory','structured','entrant_trajectory.jsonl')]],'realized_observables':{}}
    write_result(root,result)
if __name__=='__main__':main()
