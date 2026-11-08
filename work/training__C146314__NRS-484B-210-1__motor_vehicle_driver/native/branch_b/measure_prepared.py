"""Measure prepared paragraph (b) Native bodies without a legal verdict."""
import argparse
import json
from pathlib import Path

from check import check
from prepare_raw import sha, rows, read, require


def measure(bundle,saved):
    bundle,saved=map(Path,(bundle,saved))
    checked=check(bundle);cfg=read(bundle/'config.json')
    receipt=read(saved/'preparation-receipt.json')
    names=('native-observed.jsonl','camera-frames.jsonl','frame-review.jsonl')
    require(receipt['format']=='c146314-paragraph-b-raw-to-saved-v1' and
        receipt['case_id']==checked['case_id'] and
        receipt['candidate_id']==checked['candidate_id'] and
        receipt['config_sha256']==sha(bundle/'config.json') and
        receipt['saved_hashes']=={name:sha(saved/name) for name in names} and
        receipt['delivery_ready'] is False and
        receipt['legal_verdict'] is None,
        'prepared receipt/source binding')
    observed=rows(saved/names[0]);camera=rows(saved/names[1]);review=rows(saved/names[2])
    require(len(observed)==len(camera)==len(review)==240,
        'prepared frame count')
    kind=receipt['source_kind']
    require(kind in ('original_native','synthetic_cpu') and
        receipt['original_native_observed']==(kind=='original_native'),
        'prepared source kind')
    first=observed[0]['native_frame']
    parked=cfg['parked_vehicle_requested']
    pass_frames=parked_frames=reviewed_frames=0
    for i,(row,frame,view) in enumerate(zip(observed,camera,review)):
        require(row['frame']==frame['frame']==view['frame']==i and
            row['native_frame']==frame['native_frame']==view['native_frame']==first+i and
            row['time_s']==frame['time_s']==view['time_s'] and
            row['source_kind']==frame['source_kind']==view['source_kind']==kind and
            frame['video_frame']==i and
            row['observed_ego_road_id']==row['observed_lead_road_id']==211 and
            row['observed_ego_lane_id'] in (-1,-2) and
            row['observed_lead_lane_id'] in (-1,-2) and
            row['observed_parked_road_id']==(211 if parked else None) and
            row['observed_parked_lane_id']==(-2 if parked else None) and
            type(view['parked_pixel_reviewed']) is bool and
            type(view['lane_pixel_reviewed']) is bool and
            row['ego']['actor_id']!=row['lead']['actor_id'],
            f'prepared row join {i}')
        ego=row['ego'];lead=row['lead'];vehicle=row['parked_vehicle']
        require((vehicle is None)==(not parked) and
            (not parked or (vehicle['actor_id'] not in
                (ego['actor_id'],lead['actor_id']) and vehicle['speed_mps']<=.1)),
            f'parked actor state {i}')
        eb=ego['body_native_xyz_m'];lb=lead['body_native_xyz_m']
        pass_frames+=int(min(p[0] for p in eb)>max(p[0] for p in lb) and
            all(-7<=p[1]<=-3.5 for p in eb))
        parked_frames+=int(parked and vehicle is not None)
        reviewed_frames+=int(view['parked_pixel_reviewed'] and
            view['lane_pixel_reviewed'])
    return {'format':'c146314-paragraph-b-prepared-measurement-v1',
        'case_id':checked['case_id'],'candidate_id':checked['candidate_id'],
        'frames':240,'full_body_right_pass_frames':pass_frames,
        'parked_actor_frames':parked_frames,
        'human_reviewed_condition_frames':reviewed_frames,
        'source_kind':kind,'original_native_observed':kind=='original_native',
        'pavement_condition_verified':False,'legal_verdict':None,
        'delivery_ready':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--saved',type=Path,required=True)
    a=p.parse_args();print(json.dumps(measure(a.bundle,a.saved)))
