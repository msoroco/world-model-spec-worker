"""Retain a synthetic controlled traffic pair for saved comparison rehearsal."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from traffic_counterfactual import inspect


def rectangle(x,y,hx,hy):
    return [[round(x-hx,5),round(y-hy,5)],[round(x+hx,5),round(y-hy,5)],
            [round(x+hx,5),round(y+hy,5)],[round(x-hx,5),round(y+hy,5)]]


def write_rows(path,rows):
    path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))


def main():
    root=HERE/'exception-counterfactual-sources'
    absent,present=root/'absent',root/'present'
    absent.mkdir(parents=True,exist_ok=True);present.mkdir(parents=True,exist_ok=True)
    shared={'map_sha256':'1'*64,'route_sha256':'2'*64,
            'controller_sha256':'3'*64,'candidate_id':'primary','seed':'synthetic-fixed-start-v1',
            'synthetic_diagnostic':True,'physical_determinism_claimed':False}
    (absent/'capture_identity.json').write_text(json.dumps({**shared,'actor_present':False},sort_keys=True)+'\n')
    (present/'capture_identity.json').write_text(json.dumps({**shared,'actor_present':True},sort_keys=True)+'\n')
    absent_rows=[];present_rows=[];actor_rows=[]
    present_x=-20.0
    for i in range(480):
        frame=1000+i;time_s=round((i+1)*.05,5)
        absent_x=-20+.1*i
        # The actor's junction occupancy first calls for braking near frame 120.
        speed=2.0 if i<120 else max(0.0,2.0-.1*(i-119))
        if i:
            present_x+=speed*.05
        common={'native_frame':frame,'video_frame':i,'time_s':time_s,
                'native_center_xy_m':[round(absent_x,5),-1.75],
                'native_body_xy_m':rectangle(absent_x,-1.75,2.0,.9),
                'observed_speed_mps':2.0,'observed_velocity_xy_mps':[2.0,0.0],
                'applied_brake':0.0,'conflict_brake_override':False}
        absent_rows.append(common)
        present_rows.append({**common,'native_center_xy_m':[round(present_x,5),-1.75],
            'native_body_xy_m':rectangle(present_x,-1.75,2.0,.9),
            'observed_speed_mps':round(speed,5),'observed_velocity_xy_mps':[round(speed,5),0.0],
            'applied_brake':1.0 if 120<=i<140 else 0.0,
            'conflict_brake_override':120<=i<140})
        actor_y=-20+.1*i
        actor_rows.append({'native_frame':frame,'time_s':time_s,
            'center_xy_m':[0.0,round(actor_y,5)],'body_xy_m':rectangle(0,actor_y,.9,2),
            'velocity_xy_mps':[0.0,2.0]})
    write_rows(absent/'native_samples.jsonl',absent_rows)
    write_rows(present/'native_samples.jsonl',present_rows)
    write_rows(present/'other_actor_history.jsonl',actor_rows)
    result=inspect(absent,present)
    result['synthetic_diagnostic']=True
    result['source_sha256']={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob('*')) if p.is_file()}
    return result


if __name__=='__main__':
    result=main()
    out=HERE/'traffic-counterfactual-proof.json'
    out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'passed':True,'frames':result['frames'],
                      'brake_onset':result['brake_onset_video_frame'],
                      'hypothetical_overlap_count':len(result['absent_ego_present_actor_overlap_frames'])},indent=2))
