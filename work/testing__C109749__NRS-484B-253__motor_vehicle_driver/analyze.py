"""Measured left-turn yield sequence from original actor geometry; no legal verdict."""
import argparse,hashlib,json
from pathlib import Path
from worker_exchange.native_output import write_result

def source(root,name):
    p=root/name
    if not p.is_file():raise ValueError('Missing required source: '+name)
    return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]

def inside(vertices,polygon):
    xs=[p[0] for p in polygon];ys=[p[1] for p in polygon]
    return all(min(xs)<=v[0]<=max(xs) and min(ys)<=v[1]<=max(ys) for v in vertices)

def subject_interval(rows):
    samples=[{'frame':r['frame'],'time_s':r['time_s'],'inside':inside(r['ego_body_xy_m'],r['intersection_polygon_xy_m']),'speed_mps':r['ego_speed_mps'],'turn_intent':r['ego_turn_intent']} for r in rows]
    return {'samples':samples,'first_inside_time_s':next((r['time_s'] for r in samples if r['inside']),None),'measurement_scope':'sampled original frame geometry and controller intent'}

def opposing_interval(rows):
    samples=[{'frame':r['frame'],'time_s':r['time_s'],'inside':inside(r['oncoming_body_xy_m'],r['intersection_polygon_xy_m']),'speed_mps':r['oncoming_speed_mps']} for r in rows]
    return {'samples':samples,'inside_frame_count':sum(r['inside'] for r in samples)}

def yield_sequence(rows):
    overlap=[r for r in rows if inside(r['ego_body_xy_m'],r['intersection_polygon_xy_m']) and inside(r['oncoming_body_xy_m'],r['intersection_polygon_xy_m'])]
    return {'overlap_frames':[r['frame'] for r in overlap],'ego_speed_during_overlap_mps':[r['ego_speed_mps'] for r in overlap],'oncoming_clear_frame':next((r['frame'] for r in rows if not inside(r['oncoming_body_xy_m'],r['intersection_polygon_xy_m'])),None),'ego_turn_progress_frames':[r['frame'] for r in rows if r['ego_turn_progress']],'signal_states':[{'frame':r['frame'],'left_blinker':r['ego_left_blinker']} for r in rows],'immediate_hazard_threshold_applied':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    root=Path(a.attempt);case=json.loads((root/'config.json').read_text())['case']
    rows=source(root,'left253_history.jsonl')
    h=hashlib.sha256((root/'left253_history.jsonl').read_bytes()).hexdigest()
    values={'subject_inside_left_turn':{'method':'subject_interval','value':subject_interval(rows),'sources':{'left253_history.jsonl':h}},'opposing_vehicle_inside':{'method':'opposing_interval','value':opposing_interval(rows),'sources':{'left253_history.jsonl':h}},'yield_and_turn_sequence':{'method':'yield_sequence','value':yield_sequence(rows),'sources':{'left253_history.jsonl':h}}}
    Path(a.output).write_text(json.dumps({'measurements':values,'limitations':['Fixture is a three-frame diagnostic, not actual right-of-way evidence.','Signal validity and legal yield/immediate-hazard judgments remain local review.']},indent=2)+'\n')
    traces=source(root,'trace.jsonl')
    speed=[{'time_s':r['time_s'],'value':r['speed_mps']} for r in traces]
    (root/'speed.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in speed))
    for name,key in [('intersection_occupancy','subject_inside_left_turn'),('oncoming_geometry','opposing_vehicle_inside'),('yield_timing','yield_and_turn_sequence')]:
        (root/(name+'.jsonl')).write_text(''.join(json.dumps({'time_s':r['time_s'],'value':values[key]['value']})+'\n' for r in traces))
    requested=case['variable_assignments']['approach_speed_mps']['value'];measured=speed[-1]['value']
    result={'case_id':case['case_id'],'measured_values':{'approach_speed_mps':measured},'target_checks':[{'target':'approach_speed_mps','requested':requested,'measured':measured,'method':'last original velocity sample','tolerance':.1,'matched':abs(measured-requested)<=.1,'physical_cause_confirmed':False,'cause_evidence':'trace.jsonl'}],'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,'termination_reason':'diagnostic fixture only','physical_failure_flags':{'yield_verified':False},'trace_reference':'trace.jsonl','video_references':['raw.mkv'],'video_frame_map_reference':'video_frames.jsonl','recording_description':case['recording_description'],'recording_evidence':[{'name':n,'unit':u,'reference':f} for n,u,f in [('kin.speed','m/s','speed.jsonl'),('intersection_occupancy','structured','intersection_occupancy.jsonl'),('oncoming_geometry','structured','oncoming_geometry.jsonl'),('yield_timing','structured','yield_timing.jsonl')]],'realized_observables':{}}
    write_result(root,result)
if __name__=='__main__':main()
