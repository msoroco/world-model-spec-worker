"""Check exact paragraph (b) four-lane parked-vehicle request bundles."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from build import SOURCE


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines()]


def require(value, message):
    if not value:
        raise ValueError(message)


def check(bundle):
    bundle=Path(bundle)
    cfg=read(bundle/'config.json')
    plan=read(bundle/'case-plan.json')
    assignment=read(bundle/'assignment-source.json')
    source=plan['source_law']['text']
    require(source==assignment['law_record']['text'] and
        hashlib.sha256(source.encode()).hexdigest()==
        '525f777bf701d9e420e3541071bc6b10de85f747a53fb044431e00826bfee06a'
        and SOURCE in source, 'frozen paragraph (b) source')
    road=ET.parse(bundle/'four-lane-pass.xodr').getroot()
    lanes=road.findall('./road/lanes/laneSection/left/lane')+road.findall(
        './road/lanes/laneSection/right/lane')
    require(road.find('./road').attrib['id']=='211' and
        {int(l.attrib['id']) for l in lanes}=={-2,-1,1,2} and
        all(l.attrib['type']=='driving' and float(l.find('width').attrib['a'])==3.5
            for l in lanes), 'four authored driving lines')
    track=rows(bundle/'requested-tracks.jsonl')
    require(cfg['format']=='c146314-paragraph-b-request-v1' and
        cfg['assignment_sha256']==sha(bundle/'assignment-source.json') and
        cfg['case_plan_sha256']==sha(bundle/'case-plan.json') and
        cfg['road_sha256']==sha(bundle/'four-lane-pass.xodr') and
        cfg['tracks_sha256']==sha(bundle/'requested-tracks.jsonl') and
        cfg['source_branch']=='NRS 484B.210(1)(b)' and
        cfg['candidate_id'] in ('primary','fallback1','fallback2','fallback3') and
        cfg['case_id'].endswith(('__exception_2_1','__exception_2_2')) and
        cfg['parked_vehicle_requested']==cfg['case_id'].endswith('__exception_2_1') and
        cfg['frames']==240 and cfg['rate_hz']==20 and len(track)==240 and
        cfg['status']=='unselected_native_request' and
        cfg['original_native_observed'] is False and
        all(cfg[key] is False for key in ('four_driving_lanes_verified',
            'parked_vehicle_observed','pavement_unobstructed_verified',
            'actual_right_pass_observed')), 'source-bound request config')
    speed=7 if cfg['candidate_id']=='fallback1' else 8
    stop=45 if cfg['candidate_id']=='fallback3' else None
    camera='elevated_overview' if cfg['candidate_id']=='fallback2' else 'standard'
    require(cfg['requested_ego_speed_mps']==speed and cfg['stop_x_m']==stop
        and cfg['camera_policy']==camera, 'distinct candidate policy')
    passing=0
    for i,row in enumerate(track):
        t=(i+1)/20
        x=min(stop or 300,5+speed*t)
        blend=max(0,min(1,(x-15)/20,(105-x)/20))
        y=-1.75-3.5*blend
        require(row['frame']==i and row['time_s']==t and
            row['source_kind']=='authored_native_request' and
            row['source_branch']=='NRS 484B.210(1)(b)' and
            row['case_id']==cfg['case_id'] and
            row['candidate_id']==cfg['candidate_id'] and
            row['road_id']==211 and
            math.isclose(row['ego_x_m'],x,abs_tol=1e-6) and
            math.isclose(row['ego_y_m'],y,abs_tol=1e-6) and
            row['ego_lane_id']==(-2 if y < -3.5 else -1) and
            math.isclose(row['lead_x_m'],35+4*t,abs_tol=1e-6) and
            row['lead_y_m']==-1.75 and row['lead_lane_id']==-1 and
            row['parked_vehicle_requested']==cfg['parked_vehicle_requested'] and
            row['parked_x_m']==(55 if cfg['parked_vehicle_requested'] else None) and
            row['parked_y_m']==(-6.8 if cfg['parked_vehicle_requested'] else None) and
            row['parked_lane_id']==(-2 if cfg['parked_vehicle_requested'] else None) and
            all(row[key] is False for key in ('four_driving_lanes_verified',
                'parked_vehicle_observed','pavement_unobstructed_verified',
                'actual_right_pass_observed')) and row['legal_verdict'] is None,
            f'request frame {i}')
        passing+=int(row['ego_x_m']>row['lead_x_m'] and row['ego_lane_id']==-2)
    require((passing==0)==(stop is not None), 'right-pass/stop split')
    return {'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'requested_right_ahead_frames':passing,
        'four_lanes_authored':True,'parked_vehicle_requested':
            cfg['parked_vehicle_requested'],
        'original_native_observed':False,'delivery_ready':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--bundle',required=True,type=Path)
    print(json.dumps(check(parser.parse_args().bundle)))
