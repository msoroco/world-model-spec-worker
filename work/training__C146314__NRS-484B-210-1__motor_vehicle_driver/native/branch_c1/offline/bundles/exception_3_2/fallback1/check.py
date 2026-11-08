"""Check copied paragraph (c)(1) boundary request without claiming (c)(2)."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from build import SOURCE, BOUNDARY_M


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(s) for s in Path(path).read_text().splitlines()]
def require(ok,message):
    if not ok:raise ValueError(message)


def check(bundle):
    bundle=Path(bundle)
    cfg=read(bundle/'config.json')
    plan=read(bundle/'case-plan.json')
    assignment=read(bundle/'assignment-source.json')
    source=plan['source_law']['text']
    require(source==assignment['law_record']['text'] and
        hashlib.sha256(source.encode()).hexdigest()==
        '525f777bf701d9e420e3541071bc6b10de85f747a53fb044431e00826bfee06a'
        and SOURCE in source and
        'does not travel through an intersection or past any private way' in source,
        'frozen disjunctive paragraph (c) source')
    road=ET.parse(bundle/'unmarked-pass.xodr').getroot()
    lanes=road.findall('./road/lanes/laneSection/right/lane')
    require(road.find('./road').attrib['id']=='212' and
        [(int(l.attrib['id']),l.attrib['type']) for l in lanes]==
            [(-1,'driving'),(-2,'shoulder')] and
        all(float(l.find('width').attrib['a'])==3.5 for l in lanes) and
        lanes[1].find('roadMark').attrib['type']=='none',
        'unmarked authored pavement geometry')
    track=rows(bundle/'requested-tracks.jsonl')
    witness=cfg['case_id'].split('__')[-1]
    distance=61.06 if witness=='exception_3_1' else BOUNDARY_M
    speed=7 if cfg['candidate_id']=='fallback1' else 8
    stop=45 if cfg['candidate_id']=='fallback3' else None
    camera='elevated_overview' if cfg['candidate_id']=='fallback2' else 'standard'
    exit_x=20+distance
    require(witness in ('exception_3_1','exception_3_2') and
        cfg['format']=='c146314-paragraph-c1-request-v1' and
        cfg['assignment_sha256']==sha(bundle/'assignment-source.json') and
        cfg['case_plan_sha256']==sha(bundle/'case-plan.json') and
        cfg['road_sha256']==sha(bundle/'unmarked-pass.xodr') and
        cfg['tracks_sha256']==sha(bundle/'requested-tracks.jsonl') and
        cfg['source_branch']=='NRS 484B.210(1)(c)(1)' and
        cfg['requested_ego_speed_mps']==speed and
        cfg['camera_policy']==camera and cfg['stop_x_m']==stop and
        cfg['unmarked_segment_start_x_m']==20 and
        math.isclose(cfg['unmarked_segment_end_x_m'],exit_x,abs_tol=1e-6) and
        cfg['requested_excursion_m']==distance and
        cfg['requested_c1_within_200ft']==(distance<=BOUNDARY_M) and
        cfg['rate_hz']==20 and cfg['frames']==len(track)==240 and
        cfg['status']=='unselected_native_request' and
        all(cfg[k] is False for k in ('c2_crossing_verified',
            'unmarked_pavement_verified','actual_excursion_observed',
            'actual_right_pass_observed','original_native_observed')),
        'source-bound candidate and numeric boundary')
    pass_frames=0
    for i,row in enumerate(track):
        t=(i+1)/20;x=min(stop or 300,5+speed*t)
        blend=max(0,min(1,(x-15)/5,(exit_x+5-x)/5))
        y=-1.75-3.5*blend
        require(row['frame']==i and row['time_s']==t and
            row['source_kind']=='authored_native_request' and
            row['source_branch']=='NRS 484B.210(1)(c)(1)' and
            row['case_id']==cfg['case_id'] and
            row['candidate_id']==cfg['candidate_id'] and
            row['road_id']==212 and
            math.isclose(row['ego_x_m'],x,abs_tol=1e-6) and
            math.isclose(row['ego_y_m'],y,abs_tol=1e-6) and
            row['requested_surface']==('unmarked_right_pavement' if blend>=.99
                else 'driving_or_transition') and
            math.isclose(row['lead_x_m'],35+4*t,abs_tol=1e-6) and
            row['lead_y_m']==-1.75 and
            row['unmarked_segment_start_x_m']==20 and
            math.isclose(row['unmarked_segment_end_x_m'],exit_x,abs_tol=1e-6) and
            row['requested_excursion_m']==distance and
            all(row[k] is False for k in
                ('private_way_or_intersection_crossing_verified',
                 'unmarked_pavement_verified','pavement_unobstructed_verified',
                 'no_parked_vehicles_verified','actual_right_pass_observed')) and
            row['legal_verdict'] is None,
            f'authored boundary frame {i}')
        pass_frames+=int(x>row['lead_x_m'] and blend>=.99)
    require((pass_frames==0)==(stop is not None),'pass/stop request split')
    return {'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'requested_excursion_m':distance,
        'requested_c1_within_200ft':distance<=BOUNDARY_M,
        'requested_right_ahead_frames':pass_frames,
        'c2_crossing_verified':False,'original_native_observed':False,
        'delivery_ready':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    print(json.dumps(check(p.parse_args().bundle)))
