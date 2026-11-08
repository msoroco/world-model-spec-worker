"""Measure saved paragraph (b) bodies and parked occupancy without legal claims."""
import argparse
import json
import math
from pathlib import Path

from build import sha
from check import check


def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(s) for s in Path(path).read_text().splitlines()]


def measure(bundle,saved):
    bundle=Path(bundle);saved=Path(saved)
    checked=check(bundle);cfg=read(bundle/'config.json')
    receipt=read(saved/'readback.json')
    if not (receipt['source_kind']=='synthetic_cpu' and
        receipt['config_sha256']==sha(bundle/'config.json') and
        receipt['tracks_sha256']==sha(bundle/'requested-tracks.jsonl') and
        receipt['road_sha256']==sha(bundle/'four-lane-pass.xodr') and
        receipt['native_observed_sha256']==sha(saved/'native-observed.jsonl') and
        receipt['camera_frames_sha256']==sha(saved/'camera-frames.jsonl') and
        receipt['frames']==240 and receipt['original_native_observed'] is False and
        receipt['human_video_reviewed'] is False and receipt['delivery_ready'] is False):
        raise ValueError('saved paragraph (b) source binding')
    tracks=rows(bundle/'requested-tracks.jsonl')
    observed=rows(saved/'native-observed.jsonl')
    cameras=rows(saved/'camera-frames.jsonl')
    if not(len(tracks)==len(observed)==len(cameras)==240):
        raise ValueError('saved frame count')
    pass_frames=parked_frames=reviewed_frames=0
    for i,(request,row,camera) in enumerate(zip(tracks,observed,cameras)):
        if not(row['frame']==camera['frame']==i and
            row['time_s']==camera['time_s']==request['time_s'] and
            row['source_kind']==camera['source_kind']=='synthetic_cpu' and
            camera['forward_frame']==camera['overview_frame']==i and
            camera['camera_policy']==cfg['camera_policy'] and
            camera['human_reviewed'] is False and
            row['ego_actor_id']==101 and row['lead_actor_id']==102 and
            row['ego_road_id']==row['lead_road_id']==211 and
            row['ego_lane_id']==request['ego_lane_id'] and
            row['lead_lane_id']==-1 and
            row['ego_center_xy_m']==[request['ego_x_m'],request['ego_y_m']] and
            row['lead_center_xy_m']==[request['lead_x_m'],request['lead_y_m']] and
            row['pavement_unobstructed_verified'] is False and
            row['legal_verdict'] is None):
            raise ValueError(f'saved frame join {i}')
        for name in ('ego','lead'):
            x,y=row[name+'_center_xy_m'];body=row[name+'_body_xy_m']
            if body!=[[round(x+dx,6),round(y+dy,6)] for dx,dy in
                ((-2,-.9),(-2,.9),(2,.9),(2,-.9))]:
                raise ValueError(f'{name} body {i}')
        parked=cfg['parked_vehicle_requested']
        if not(row['parked_actor_id']==(103 if parked else None) and
            row['parked_center_xy_m']==([55,-6.8] if parked else None) and
            row['parked_speed_mps']==(0 if parked else None) and
            row['parked_lane_id']==(-2 if parked else None) and
            row['parked_pixels_reviewed'] is False and
            row['lane_pixels_reviewed'] is False):
            raise ValueError(f'parked observation {i}')
        if parked:
            x,y=row['parked_center_xy_m']
            if row['parked_body_xy_m']!=[[round(x+dx,6),round(y+dy,6)]
                for dx,dy in ((-2,-.9),(-2,.9),(2,.9),(2,-.9))]:
                raise ValueError(f'parked body {i}')
        elif row['parked_body_xy_m'] is not None:
            raise ValueError(f'unexpected parked body {i}')
        ego=row['ego_body_xy_m'];lead=row['lead_body_xy_m']
        pass_frames+=int(min(p[0] for p in ego)>max(p[0] for p in lead)
            and all(-7<=p[1]<=-3.5 for p in ego))
        parked_frames+=int(parked and row['parked_body_xy_m'] is not None)
        reviewed_frames+=int(row['parked_pixels_reviewed'] and row['lane_pixels_reviewed'])
    return {'format':'c146314-paragraph-b-saved-measurement-v1',
        'case_id':checked['case_id'],'candidate_id':checked['candidate_id'],
        'frames':240,'full_body_right_pass_frames':pass_frames,
        'synthetic_parked_body_frames':parked_frames,
        'human_reviewed_condition_frames':reviewed_frames,
        'source_kind':'synthetic_cpu','original_native_observed':False,
        'pavement_unobstructed_verified':False,'legal_verdict':None,
        'delivery_ready':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--saved',type=Path,required=True);a=p.parse_args()
    print(json.dumps(measure(a.bundle,a.saved)))
