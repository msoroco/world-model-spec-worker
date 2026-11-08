"""Check copied C146314 request sources and every authored trajectory row."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def require(ok,message):
    if not ok:raise ValueError(message)


def check(bundle):
    bundle=Path(bundle)
    cfg=read(bundle/'config.json')
    law=read(bundle/'assignment-source.json')
    plan=read(bundle/'case-plan.json')
    track=bundle/'requested-tracks.jsonl';road=bundle/'one-way-pass.xodr'
    witness=cfg['case_id'].removeprefix(cfg['assignment_id']+'__')
    candidate=cfg['candidate_id']
    require(cfg['assignment_id']==law['assignment_id']==plan['assignment_id'] and
            cfg['law_id']==law['law_id']=='NRS-484B-210-1' and
            cfg['cell_id']==law['cell_id']=='C146314' and
            cfg['actor']==law['actor']=='motor_vehicle_driver' and
            cfg['assignment_sha256']==sha(bundle/'assignment-source.json') and
            cfg['case_plan_sha256']==sha(bundle/'case-plan.json') and
            cfg['road_sha256']==sha(road) and
            cfg['tracks_sha256']==sha(track) and
            cfg['frames']==240 and cfg['rate_hz']==20 and
            cfg['status']=='unselected_native_request' and
            cfg['original_native_observed'] is False and
            cfg['actual_right_pass_observed'] is False and
            witness in ('witness_1','witness_2') and
            candidate in ('primary','fallback1','fallback2','fallback3'),
            'source/config binding')
    require(plan['source_law']['text']==law['law_record']['text'] and
            'Upon any highway on which traffic is restricted to one direction'
            in law['law_record']['text'], 'frozen paragraph d')
    root=ET.parse(road).getroot();roads=root.findall('road')
    require(len(roads)==1 and roads[0].get('id')=='210' and
            roads[0].get('length')=='300' and
            {int(l.get('id')):float(l.find('width').get('a')) for l in
             roads[0].findall('./lanes/laneSection/right/lane')}==
            {-1:3.5,-2:3.5}, 'one-way road request')
    speed=7 if candidate=='fallback1' else 8
    stop=45 if candidate=='fallback3' else None
    obstruction=witness=='witness_2'
    require(cfg['requested_ego_speed_mps']==speed and
            cfg['stop_x_m']==stop and
            cfg['camera_policy']==('elevated_overview' if
                                   candidate=='fallback2' else 'standard') and
            cfg['right_lane_obstruction_requested']==obstruction and
            cfg['obstruction_x_m']==(55 if obstruction else None) and
            cfg['obstruction_y_m']==(-6.8 if obstruction else None) and
            cfg['obstruction_radius_m']==(.2 if obstruction else None),
            'candidate/witness policy')
    data=rows(track);require(len(data)==240,'request frame coverage')
    for i,row in enumerate(data):
        t=(i+1)/20;x=min(stop or 300,speed*t)
        right=max(0,min(1,(x-15)/20,(105-x)/20))
        y=-1.75-3.5*right
        phase='approach' if x<15 else 'right_excursion' if x<85 else 'return'
        require(row['frame']==i and row['time_s']==t and
                row['case_id']==cfg['case_id'] and
                row['candidate_id']==candidate and
                row['source_kind']=='authored_native_request' and
                row['road_id']==210 and row['phase']==phase and
                math.isclose(row['ego_x_m'],x,abs_tol=1e-6) and
                math.isclose(row['ego_y_m'],y,abs_tol=1e-6) and
                row['ego_lane_id']==(-2 if y<-3.5 else -1) and
                math.isclose(row['lead_x_m'],30+4*t,abs_tol=1e-6) and
                row['lead_y_m']==-1.75 and row['lead_lane_id']==-1 and
                row['right_lane_obstruction_requested']==obstruction and
                row['obstruction_x_m']==(55 if obstruction else None) and
                row['obstruction_y_m']==(-6.8 if obstruction else None) and
                row['obstruction_radius_m']==(.2 if obstruction else None) and
                row['one_way_designation_verified'] is False and
                row['unobstructed_pavement_verified'] is False and
                row['actual_right_pass_observed'] is False and
                row['legal_verdict'] is None, f'request frame {i}')
    return {'case_id':cfg['case_id'],'candidate_id':candidate,'frames':240,
            'source_bound':True,'original_native_observed':False,
            'delivery_ready':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    print(json.dumps(check(p.parse_args().bundle)))
