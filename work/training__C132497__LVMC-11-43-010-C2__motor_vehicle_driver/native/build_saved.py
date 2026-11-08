"""Retain explicitly synthetic saved observations for every right-exit request."""
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]

def build():
    entries=[]
    for witness in ('reference','contrast'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            source=HERE/'drafts'/witness/candidate
            cfg=json.loads((source/'config.json').read_text())
            requests=rows(source/'requested-tracks.jsonl')
            target=HERE/'saved-fixtures'/witness/candidate
            target.mkdir(parents=True,exist_ok=True)
            observed=[];camera=[]
            for row in requests:
                i=row['frame'];heading=math.radians(row['ego_heading_deg'])
                c,s=math.cos(heading),math.sin(heading)
                x,y=row['ego_x_m'],row['ego_y_m']
                body=[[round(x+a*c-b*s,6),round(y+a*s+b*c,6)]
                    for a,b in ((-1,-.5),(-1,.5),(1,-.5),(1,.5))]
                observed.append({'frame':i,'native_frame':1000+i,'time_s':row['time_s'],
                    'source_kind':'synthetic_cpu','witness':witness,'candidate_id':candidate,
                    'phase':row['phase'],'road_id':row['road_id'],'lane_id':row['lane_id'],
                    'ego_x_m':x,'ego_y_m':y,'ego_heading_deg':row['ego_heading_deg'],
                    'ego_speed_mps':row['ego_speed_mps'],'ego_body_xy_m':body,
                    'actual_exit_observed':False})
                camera.append({'frame':i,'camera_frame':1000+i,
                    'time_s':row['time_s'],'source_kind':'synthetic_cpu',
                    'right_lane_visible':True})
            (target/'native-observed.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in observed))
            (target/'camera-frames.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in camera))
            readback={'source_kind':'synthetic_cpu','road_sha256':cfg['road_sha256'],
                'request_sha256':cfg['tracks_sha256'],'right_lane_id':-2,
                'other_lane_id':-1,'physical_roundabout_verified':False,
                'lane_allocation_verified':False,'actual_right_exit_verified':False}
            (target/'lane-readback.json').write_text(json.dumps(readback,indent=2)+'\n')
            entries.append({'witness':witness,'candidate_id':candidate,
                'sha256':{name:sha(target/name) for name in
                    ('native-observed.jsonl','camera-frames.jsonl','lane-readback.json')}})
    manifest={'format':'c132497-synthetic-saved-v1','entries':entries,
        'original_native_observed':False,'delivery_ready':False}
    (HERE/'saved-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':print(json.dumps({'fixtures':len(build()['entries'])}))
