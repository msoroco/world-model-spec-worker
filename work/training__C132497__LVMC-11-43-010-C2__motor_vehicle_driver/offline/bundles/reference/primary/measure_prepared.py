"""Measure a prepared original or synthetic right-exit observation without promotion."""
import argparse
import hashlib
import json
import math
from pathlib import Path

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path): return [json.loads(s) for s in Path(path).read_text().splitlines()]
def finite(x): return type(x) in (int,float) and math.isfinite(x)

def measure(bundle,saved):
    bundle,saved=Path(bundle),Path(saved)
    cfg=json.loads((bundle/'config.json').read_text())
    receipt=json.loads((saved/'preparation-receipt.json').read_text())
    readback=json.loads((saved/'lane-readback.json').read_text())
    request=rows(bundle/'requested-tracks.jsonl')
    observed=rows(saved/'native-observed.jsonl')
    camera=rows(saved/'camera-frames.jsonl')
    hashes={name:sha(saved/name) for name in
        ('native-observed.jsonl','camera-frames.jsonl','lane-readback.json')}
    kind=readback.get('source_kind')
    if (kind not in ('synthetic_cpu','original_native') or
        cfg['tracks_sha256']!=sha(bundle/'requested-tracks.jsonl') or
        cfg['road_sha256']!=sha(bundle/'right-exit-road.xodr') or
        receipt.get('saved_hashes')!=hashes or
        receipt.get('case_id')!=cfg['case_id'] or
        receipt.get('candidate_id')!=cfg['candidate_id'] or
        receipt.get('source_kind')!=kind or
        receipt.get('original_native_observed')!=(kind=='original_native') or
        receipt.get('delivery_ready') is not False or
        readback.get('road_sha256')!=cfg['road_sha256'] or
        readback.get('request_sha256')!=cfg['tracks_sha256'] or
        readback.get('right_lane_id')!=-2 or
        readback.get('other_lane_id')!=-1 or
        readback.get('review_provenance')!=
            ('human_frame_review' if kind=='original_native' else 'synthetic_cpu') or
        readback.get('physical_roundabout_verified') is not False or
        readback.get('lane_allocation_verified') is not False or
        readback.get('actual_right_exit_verified') is not False or
        not (len(request)==len(observed)==len(camera)==240)):
        raise ValueError('C132497 prepared provenance differs')
    counts={'entry':0,'circulation':0,'exit':0}
    body_frames=0;visible=0;prior=None;last_phase=-1
    first_native=observed[0].get('native_frame')
    if type(first_native) is not int:raise ValueError('C132497 native frame absent')
    headings={'entry':[],'exit':[]}
    for i,(req,row,frame) in enumerate(zip(request,observed,camera)):
        road=row.get('road_id');phase={20:'entry',21:'circulation',22:'exit'}.get(road)
        rank={'entry':0,'circulation':1,'exit':2}.get(phase,-1)
        if (req.get('frame')!=i or row.get('frame')!=i or frame.get('frame')!=i or
            row.get('native_frame')!=first_native+i or
            frame.get('camera_frame')!=first_native+i or
            row.get('time_s')!=(i+1)/20 or frame.get('time_s')!=row['time_s'] or
            row.get('source_kind')!=kind or frame.get('source_kind')!=kind or
            row.get('witness')!=req.get('witness') or
            row.get('candidate_id')!=cfg['candidate_id'] or
            row.get('lane_id')!=cfg['requested_lane_id'] or
            row.get('ego_actor_id')!=readback.get('ego_actor_id') or
            row.get('ego_blueprint')!='vehicle.tesla.model3' or
            row.get('phase')!=phase or rank<last_phase or
            row.get('actual_exit_observed')!=(kind=='original_native' and road==22) or
            type(frame.get('right_lane_visible')) is not bool or
            not all(finite(row.get(k)) for k in
                ('ego_x_m','ego_y_m','ego_heading_deg','ego_speed_mps')) or
            row['ego_speed_mps']<0):
            raise ValueError(f'C132497 prepared frame differs at {i}')
        last_phase=rank;counts[phase]+=1
        if phase in headings:headings[phase].append(row['ego_heading_deg'])
        x,y=row['ego_x_m'],row['ego_y_m']
        if prior is not None and abs(20*math.hypot(x-prior[0],y-prior[1])-row['ego_speed_mps'])>.65:
            raise ValueError('C132497 observed displacement differs')
        prior=(x,y)
        body=row.get('ego_body_xy_m')
        if (not isinstance(body,list) or len(body)!=8 or any(
            not isinstance(p,list) or len(p)!=2 or not all(map(finite,p)) or
            math.hypot(p[0]-x,p[1]-y)>1.3 for p in body)):
            raise ValueError('C132497 observed body differs')
        if kind=='synthetic_cpu' and any(abs(row['ego_'+key]-req['ego_'+key])>1e-5
            for key in ('x_m','y_m','heading_deg','speed_mps')):
            raise ValueError('C132497 synthetic prepared request differs')
        if phase=='circulation':
            lower,upper=((15,18.5) if row['lane_id']==-2 else (18.5,22))
            if all(lower<=math.hypot(p[0]-22,p[1]+22)<=upper for p in body):
                body_frames+=1
        if frame['right_lane_visible']:visible+=1
    if receipt.get('observed_exit_road_frames')!=counts['exit']:
        raise ValueError('C132497 prepared exit count differs')
    if cfg['candidate_id']=='fallback3':
        if counts['circulation'] or counts['exit']:
            raise ValueError('C132497 stop fallback passed entry')
    elif not all(counts.values()):
        raise ValueError('C132497 observed route lacks a phase')
    if body_frames!=counts['circulation']:
        raise ValueError('C132497 observed circulating body left lane')
    heading_change=None
    if counts['exit']:
        a,b=map(math.radians,(headings['entry'][0],headings['exit'][-1]))
        heading_change=math.degrees(math.atan2(math.sin(b-a),math.cos(b-a)))
        if not -120<=heading_change<=-60:
            raise ValueError('C132497 observed right exit heading differs')
    return {'format':'c132497-prepared-saved-measurement-v1',
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'source_kind':kind,'phase_frames':counts,
        'full_body_circulation_lane_frames':body_frames,
        'right_lane_visible_frames':visible,
        'observed_heading_change_deg':heading_change,
        'actual_right_exit_observed':kind=='original_native' and counts['exit']>0,
        'physical_roundabout_verified':False,'legal_verdict':None,
        'delivery_ready':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--saved-dir',type=Path,required=True);a=p.parse_args()
    print(json.dumps(measure(a.bundle,a.saved_dir)))
