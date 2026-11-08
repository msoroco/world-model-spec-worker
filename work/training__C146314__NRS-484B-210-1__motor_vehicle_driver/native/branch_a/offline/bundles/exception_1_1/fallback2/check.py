"""Check exact copied C146314 paragraph (a) signal-pair request bundles."""
import argparse
import hashlib
import json
import math
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def require(ok,message):
    if not ok:raise ValueError(message)

def check(bundle):
    bundle=Path(bundle);cfg=read(bundle/'config.json')
    plan=read(bundle/'case-plan.json');assignment=read(bundle/'assignment-source.json')
    track=rows(bundle/'requested-tracks.jsonl')
    source=plan['source_law']['text']
    require(source==assignment['law_record']['text'] and
        hashlib.sha256(source.encode()).hexdigest()==
            '525f777bf701d9e420e3541071bc6b10de85f747a53fb044431e00826bfee06a' and
        'When the driver of the vehicle overtaken is making or signaling to make a left turn.' in source,
        'paragraph (a) frozen source')
    require(cfg['format']=='c146314-paragraph-a-request-v1' and
        cfg['assignment_sha256']==sha(bundle/'assignment-source.json') and
        cfg['case_plan_sha256']==sha(bundle/'case-plan.json') and
        cfg['road_sha256']==sha(bundle/'one-way-pass.xodr') and
        cfg['tracks_sha256']==sha(bundle/'requested-tracks.jsonl') and
        cfg['source_branch']=='NRS 484B.210(1)(a)' and
        cfg['candidate_id'] in ('primary','fallback1','fallback2','fallback3') and
        cfg['case_id'].endswith(('__exception_1_1','__exception_1_2')) and
        cfg['lead_left_signal_requested']==cfg['case_id'].endswith('__exception_1_2') and
        cfg['right_lane_obstruction_requested'] is False and
        cfg['status']=='unselected_native_request' and
        cfg['original_native_observed'] is False and len(track)==240,
        'paragraph (a) config/source binding')
    speed=7 if cfg['candidate_id']=='fallback1' else 8
    stop=45 if cfg['candidate_id']=='fallback3' else None
    camera='elevated_overview' if cfg['candidate_id']=='fallback2' else 'standard'
    require(cfg['requested_ego_speed_mps']==speed and
            cfg['stop_x_m']==stop and cfg['camera_policy']==camera,
            'fallback policy')
    passing=0
    for i,row in enumerate(track):
        t=(i+1)/20;x=min(stop or 300,5+speed*t)
        blend=max(0,min(1,(x-15)/20,(105-x)/20))
        require(row['frame']==i and row['time_s']==t and
            row['source_kind']=='authored_native_request' and
            row['case_id']==cfg['case_id'] and
            row['candidate_id']==cfg['candidate_id'] and
            row['source_branch']=='NRS 484B.210(1)(a)' and
            row['lead_left_signal_requested']==cfg['lead_left_signal_requested'] and
            row['road_id']==210 and
            math.isclose(row['ego_x_m'],x,abs_tol=1e-6) and
            math.isclose(row['ego_y_m'],-1.75-3.5*blend,abs_tol=1e-6) and
            math.isclose(row['lead_x_m'],35+4*t,abs_tol=1e-6) and
            row['lead_y_m']==-1.75 and
            row['right_lane_obstruction_requested'] is False and
            row['obstruction_x_m'] is None and
            row['actual_right_pass_observed'] is False and
            row['legal_verdict'] is None,
            f'paragraph (a) request frame {i}')
        passing+=int(row['ego_x_m']>row['lead_x_m'] and row['ego_lane_id']==-2)
    require((passing==0)==(stop is not None),'requested pass/stop split')
    return {'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'source_bound':True,'lead_left_signal_requested':
            cfg['lead_left_signal_requested'],
        'requested_right_ahead_frames':passing,
        'original_native_observed':False,'delivery_ready':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    a=p.parse_args();print(json.dumps(check(a.bundle)))
