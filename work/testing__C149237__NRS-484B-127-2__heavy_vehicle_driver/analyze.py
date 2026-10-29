"""Saved-only 500 ft truck gap and width evidence; no statutory verdict."""
import argparse, hashlib, json, math
from pathlib import Path
from worker_exchange.native_output import write_result
from following_controller import along_route_body_gap

def required(root,name):
    p=root/name
    if not p.is_file():raise ValueError('Missing required source: '+name)
    return p

def body_gap(root):
    rows=[json.loads(s) for s in required(root,'truck_history.jsonl').read_text().splitlines() if s]
    if not rows:raise ValueError('No full-body truck samples')
    gaps=[]
    for row in rows:
        ego,lead=row['ego_vertices_m'],row['lead_vertices_m']
        if len(ego)!=8 or len(lead)!=8:raise ValueError('Require all eight body vertices per truck')
        gap=along_route_body_gap(ego,lead)
        if not math.isfinite(gap):raise ValueError('Nonfinite truck body gap')
        gaps.append({'frame':row['frame'],'time_s':row['time_s'],'along_route_body_gap_m':gap})
    return {'samples':gaps,'minimum_m':min(r['along_route_body_gap_m'] for r in gaps),
            'maximum_m':max(r['along_route_body_gap_m'] for r in gaps),
            '500ft_m':152.4,'above_500ft_original_frames':[r['frame'] for r in gaps if r['along_route_body_gap_m']>=152.4],
            'sampling_limit':'Original 20 Hz full vertices projected to 3D crest centerline arc; between-frame gaps unverified'}

def truck_width_and_lanes(root):
    value=json.loads(required(root,'truck_context.json').read_text())
    if len(value.get('trucks',[]))!=2 or not value.get('same_direction_lane_count'):
        raise ValueError('Incomplete truck/lane context')
    return {'trucks':value['trucks'],'same_direction_lane_count':value['same_direction_lane_count'],
            '80in_m':2.032,'source':value['source'],'qualification_unconfirmed':True}

def finalize(root,output):
    cfg=json.loads(required(root,'config.json').read_text());gap=body_gap(root);context=truck_width_and_lanes(root)
    measurements={}
    for key,method,value,source in [('truck_body_gap','body_gap',gap,'truck_history.jsonl'),
                                     ('truck_width_and_lanes','truck_width_and_lanes',context,'truck_context.json')]:
        measurements[key]={'method':method,'value':value,'sources':{source:hashlib.sha256(required(root,source).read_bytes()).hexdigest()}}
    output.write_text(json.dumps({'format':'worker-analysis-report-v1','case_id':cfg['selected_case_id'],'measurements':measurements,
      'limitations':['Fixture is diagnostic only.','Truck width, route, overtaking opportunity and 500 ft space require Native and legal review.']},indent=2)+'\n')
    rows=[json.loads(s) for s in required(root,'trace.jsonl').read_text().splitlines() if s]
    channels=root/'channels';channels.mkdir(exist_ok=True)
    (channels/'kin.speed.jsonl').write_text(''.join(json.dumps({'time_s':r['time_s'],'value':r['speed_mps']})+'\n' for r in rows))
    target=cfg['case']['variable_assignments']['requested_body_gap_m']['value']
    result={'case_id':cfg['selected_case_id'],'measured_values':{'minimum_body_gap_m':gap['minimum_m']},
      'target_checks':[{'target':'observed_body_gap_m','requested':target,'measured':gap['minimum_m'],'method':'full-body extrema along directed road',
        'tolerance':20,'matched':abs(gap['minimum_m']-target)<=20,'physical_cause_confirmed':False,'cause_evidence':'truck_history.jsonl'}],
      'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,'termination_reason':'saved diagnostic only',
      'physical_failure_flags':{'detection_validated':False},'trace_reference':'trace.jsonl','video_references':['raw.mkv'],
      'video_frame_map_reference':'video_frames.jsonl','recording_description':cfg['case']['recording_description'],
      'recording_evidence':[{'name':'kin.speed','unit':'m/s','reference':'channels/kin.speed.jsonl'}], 'realized_observables':{}}
    write_result(root,result)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True)
 a=p.parse_args();finalize(Path(a.attempt),Path(a.output))
