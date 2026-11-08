"""Create explicitly synthetic saved observations for paragraph (b) CPU checks."""
import json
from pathlib import Path

from build import HERE, sha, put, put_rows


def box(x,y):
    return [[round(x+dx,6),round(y+dy,6)]
        for dx,dy in ((-2,-.9),(-2,.9),(2,.9),(2,-.9))]


def build():
    manifest=json.loads((HERE/'manifest.json').read_text())
    for entry in manifest['entries']:
        witness=entry['case_id'].split('__')[-1]
        candidate=entry['candidate_id']
        draft=HERE/'drafts'/witness/candidate
        target=HERE/'saved-fixtures'/witness/candidate
        cfg=json.loads((draft/'config.json').read_text())
        requests=[json.loads(s) for s in (draft/'requested-tracks.jsonl').read_text().splitlines()]
        observed=[];camera=[]
        for row in requests:
            parked=cfg['parked_vehicle_requested']
            observed.append({'frame':row['frame'],'time_s':row['time_s'],
                'source_kind':'synthetic_cpu','ego_actor_id':101,
                'lead_actor_id':102,'parked_actor_id':103 if parked else None,
                'ego_road_id':211,'lead_road_id':211,
                'ego_lane_id':row['ego_lane_id'],'lead_lane_id':-1,
                'ego_center_xy_m':[row['ego_x_m'],row['ego_y_m']],
                'lead_center_xy_m':[row['lead_x_m'],row['lead_y_m']],
                'ego_body_xy_m':box(row['ego_x_m'],row['ego_y_m']),
                'lead_body_xy_m':box(row['lead_x_m'],row['lead_y_m']),
                'parked_center_xy_m':[55,-6.8] if parked else None,
                'parked_body_xy_m':box(55,-6.8) if parked else None,
                'parked_speed_mps':0 if parked else None,
                'parked_lane_id':-2 if parked else None,
                'parked_pixels_reviewed':False,
                'lane_pixels_reviewed':False,
                'pavement_unobstructed_verified':False,
                'legal_verdict':None})
            camera.append({'frame':row['frame'],'time_s':row['time_s'],
                'source_kind':'synthetic_cpu','forward_frame':row['frame'],
                'overview_frame':row['frame'],
                'camera_policy':cfg['camera_policy'],
                'human_reviewed':False})
        put_rows(target/'native-observed.jsonl',observed)
        put_rows(target/'camera-frames.jsonl',camera)
        put(target/'readback.json',{
            'format':'c146314-paragraph-b-synthetic-readback-v1',
            'source_kind':'synthetic_cpu','config_sha256':sha(draft/'config.json'),
            'tracks_sha256':sha(draft/'requested-tracks.jsonl'),
            'road_sha256':sha(HERE/'four-lane-pass.xodr'),
            'native_observed_sha256':sha(target/'native-observed.jsonl'),
            'camera_frames_sha256':sha(target/'camera-frames.jsonl'),
            'frames':240,'original_native_observed':False,
            'human_video_reviewed':False,'delivery_ready':False})
    return {'fixtures':len(manifest['entries'])}


if __name__=='__main__':print(json.dumps(build()))
