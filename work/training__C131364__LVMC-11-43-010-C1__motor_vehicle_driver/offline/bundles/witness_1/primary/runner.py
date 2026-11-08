"""Check an exact copied C131364 Native request without importing CARLA."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def check(bundle):
    bundle=Path(bundle)
    config=json.loads((bundle/'config.json').read_text())
    source=json.loads((bundle/'assignment-source.json').read_text())
    plan=json.loads((bundle/'case-plan.json').read_text())
    witness=config.get('case_id','').removeprefix(config.get('assignment_id','')+'__')
    candidate=config.get('candidate_id')
    if (config.get('format')!='c131364-roundabout-lane-request-v1' or
        source.get('assignment_id')!=config.get('assignment_id') or
        plan.get('assignment_id')!=config.get('assignment_id') or
        config['case_id'] not in {row['case_id'] for row in plan['cases']} or
        witness not in ('witness_1','witness_2') or
        candidate not in ('primary','fallback1','fallback2','fallback3') or
        config.get('law_id')!='LVMC-11-43-010-C1' or
        config.get('cell_id')!='C131364' or
        config.get('rate_hz')!=20 or config.get('frames')!=240 or
        config.get('actual_left_exit_observed') is not False or
        config.get('exit_connector_verified') is not False or
        config.get('roundabout_verified') is not False or
        config.get('status')!='unselected_native_request'):
        raise ValueError('C131364 exact request scope differs')
    for key,name in {'assignment_sha256':'assignment-source.json',
                     'case_plan_sha256':'case-plan.json',
                     'road_sha256':'road.xodr',
                     'tracks_sha256':'requested-tracks.jsonl'}.items():
        if config.get(key)!=sha(bundle/name):
            raise ValueError('C131364 exact source hash differs')
    xml=ET.parse(bundle/'road.xodr').getroot()
    lanes={int(row.attrib['id']):row.attrib['type'] for row in xml.findall('.//lane')}
    if lanes!={0:'none',-1:'driving',-2:'driving'}:
        raise ValueError('C131364 two-lane map differs')
    lane,radius=(-1,23.75) if witness=='witness_1' else (-2,27.25)
    speed=6.5 if candidate=='fallback1' else 3 if candidate=='fallback3' else 8
    camera='elevated_overview_plus_four' if candidate=='fallback2' else 'four_views'
    if (config['requested_lane_id']!=lane or config['requested_lane_radius_m']!=radius or
        config['camera_policy']!=camera):
        raise ValueError('C131364 lane or camera policy differs')
    rows=[json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    if len(rows)!=240:raise ValueError('C131364 frame count differs')
    for i,row in enumerate(rows):
        time_s=(i+1)/20
        travel=min(12,speed*time_s) if candidate=='fallback3' else speed*time_s
        theta=-math.pi/2+travel/radius
        if (row.get('frame')!=i or abs(row.get('time_s',-1)-time_s)>1e-6 or
            row.get('witness')!=witness or row.get('candidate_id')!=candidate or
            row.get('lane_id')!=lane or row.get('requested_radius_m')!=radius or
            abs(row.get('ego_x_m',1e9)-radius*math.cos(theta))>1e-5 or
            abs(row.get('ego_y_m',1e9)-radius*math.sin(theta))>1e-5 or
            abs(row.get('ego_heading_deg',1e9)-round(math.degrees(theta+math.pi/2)%360,6))>1e-5 or
            row.get('ego_speed_mps')!=(0 if candidate=='fallback3' and speed*time_s>12 else speed) or
            row.get('actual_exit_observed') is not False):
            raise ValueError(f'C131364 copied request row differs at {i}')
    return {'format':'c131364-copied-runner-check-v1','case_id':config['case_id'],
            'candidate_id':candidate,'requested_frames':240,
            'carla_imported':False,'actual_exit_observed':False,
            'delivery_ready':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true',required=True)
    parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(check(args.bundle)))
