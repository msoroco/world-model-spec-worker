"""Synthetic raw-to-saved U-turn measurements, with no district or legal claim."""
import json
import math
from pathlib import Path

from build import CASES, FRAMES, HERE, POLICIES, RATE, put, sha
from check import check


def body(center, heading):
    x,y,z=center;c,s=math.cos(heading),math.sin(heading)
    return [[round(x+dx*c-dy*s,6),round(y+dx*s+dy*c,6),round(z+dz,6)]
            for dx in (-2,2) for dy in (-.9,.9) for dz in (-.7,.7)]


def make_raw(bundle):
    bundle=Path(bundle)
    cfg=json.loads((bundle/'config.json').read_text())
    requests=[json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    output=[]
    for i,row in enumerate(requests):
        center=row['requested_ego_xyz_m'];next_center=requests[min(i+1,FRAMES-1)]['requested_ego_xyz_m']
        velocity=[round((next_center[k]-center[k])*RATE,6) for k in range(3)]
        output.append({'frame':i,'video_frame':i,'time_s':row['time_s'],'request_frame':i,
                       'source_kind':'synthetic_fixture',
                       'ego':{'actor_id':10,'blueprint':cfg['ego_blueprint'],'center_xyz_m':center,
                              'heading_rad':row['requested_heading_rad'],
                              'velocity_xyz_mps':velocity,'speed_mps':round(math.sqrt(sum(v*v for v in velocity)),6),
                              'body_xyz_m':body(center,row['requested_heading_rad'])},
                       'requested_phase':row['requested_phase'],
                       'authored_business_district':True,'district_designation_verified':False,
                       'original_native_observed':False,'legal_verdict':None})
    return {'format':'c111662-4033-synthetic-raw-v1','case_id':cfg['case_id'],
            'candidate_id':cfg['candidate_id'],'config_sha256':sha(bundle/'config.json'),
            'tracks_sha256':sha(bundle/'requested-tracks.jsonl'),
            'rows':output,'synthetic':True,'original_native_observed':False}


def process(bundle,raw_path):
    bundle,raw_path=Path(bundle),Path(raw_path)
    check(bundle)
    cfg=json.loads((bundle/'config.json').read_text())
    raw=json.loads(raw_path.read_text())
    if raw!=make_raw(bundle) or len(raw.get('rows',[]))!=FRAMES:
        raise ValueError('Source, frame, actor body or video join changed')
    rows=raw['rows']
    turn=[row for row in rows if row['requested_phase']=='u_turn']
    if len(turn)<90 or max(row['ego']['heading_rad'] for row in turn)<math.pi-.04:
        raise ValueError('Heading reversal not measured')
    crossing=next((row for row in turn if row['ego']['center_xyz_m'][1]>=0),None)
    if crossing is None:
        raise ValueError('Centerline crossing missing')
    center=cfg['requested_turn_center_x_m']
    if abs(crossing['ego']['center_xyz_m'][0]-(center+6.0))>.05:
        raise ValueError('Turning arc centerline crossing changed')
    turn_end=next((row for row in rows if row['requested_phase']=='westbound_departure'),None)
    if turn_end is None:
        raise ValueError('Return heading missing')
    dwell=sum(row['requested_phase']=='pre_turn_dwell' for row in rows)
    return {'format':'c111662-4033-synthetic-saved-v1','case_id':cfg['case_id'],
            'candidate_id':cfg['candidate_id'],'raw_sha256':sha(raw_path),'frames_joined':FRAMES,
            'u_turn_frames':len(turn),'centerline_crossing_frame':crossing['frame'],
            'centerline_crossing_x_m':crossing['ego']['center_xyz_m'][0],
            'turn_center_x_m':center,'authored_intersection_zone_x_m':[-20,20],
            'authored_at_intersection':-20<=center<=20,
            'observed_heading_reversal_rad':round(turn_end['ego']['heading_rad'],6),
            'pre_turn_stationary_frames':dwell,
            'district_designation_verified':False,'intersection_exception_legally_verified':False,
            'synthetic':True,'original_native_observed':False,'legal_verdict':None,
            'delivery_ready':False}


def build_saved():
    entries=[]
    for suffix in CASES:
        for candidate in POLICIES:
            bundle=HERE/'drafts'/suffix/candidate
            raw=HERE/'synthetic'/suffix/candidate/'raw.json'
            saved=raw.parent/'saved.json'
            put(raw,make_raw(bundle));put(saved,process(bundle,raw))
            entries.append({'case_suffix':suffix,'candidate_id':candidate,
                            'raw_sha256':sha(raw),'saved_sha256':sha(saved)})
    put(HERE/'saved-manifest.json',{'format':'c111662-4033-synthetic-saved-manifest-v1',
                                  'entries':entries,'original_native_observed':False})
    return entries


if __name__=='__main__':print(json.dumps({'processed':len(build_saved())}))
