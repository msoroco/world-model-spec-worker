"""CPU exact-bundle checker for unselected rotary Native requests."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def check(bundle):
    bundle=Path(bundle)
    config=json.loads((bundle/'config.json').read_text())
    assignment=json.loads((bundle/'assignment-source.json').read_text())
    plan=json.loads((bundle/'case-plan.json').read_text())
    case=config.get('island_side_request')
    candidate=config.get('candidate_id')
    if (config.get('format')!='c234827-native-request-v1' or
            assignment.get('assignment_id')!=config.get('assignment_id') or
            plan.get('assignment_id')!=config.get('assignment_id') or
            case not in ('reference','contrast') or
            candidate not in ('primary','fallback1','fallback2','fallback3') or
            config.get('case_id')!=config['assignment_id']+'__'+case or
            config['case_id'] not in {row['case_id'] for row in plan['cases']} or
            config.get('status')!='unselected_native_request' or
            config.get('physical_island_verified') is not False or
            config.get('frames')!=240 or config.get('rate_hz')!=20):
        raise ValueError('Exact rotary bundle case differs')
    paths={'assignment_sha256':'assignment-source.json',
           'case_plan_sha256':'case-plan.json','road_sha256':'road.xodr',
           'island_geometry_sha256':'island-geometry.json',
           'tracks_sha256':'requested-tracks.jsonl'}
    if any(config.get(key)!=sha(bundle/name) for key,name in paths.items()):
        raise ValueError('Exact rotary source hash differs')
    road=ET.parse(bundle/'road.xodr').getroot()
    arc=road.find('./road/planView/geometry/arc')
    lanes={int(item.attrib['id']):item.attrib['type'] for item in road.findall('.//lane')}
    island=json.loads((bundle/'island-geometry.json').read_text())
    if (lanes!={0:'none',-1:'driving',-2:'driving'} or
            abs(float(arc.attrib['curvature'])-1/22)>1e-9 or
            island['center_xy_m']!=[0,0] or
            island['requested_island_radius_m']!=15 or
            island['physical_island_verified']):
        raise ValueError('Rotary road or island request differs')
    rows=[json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    if len(rows)!=240:raise ValueError('Rotary request row count differs')
    direction=1 if case=='reference' else -1
    start=-math.pi/2 if case=='reference' else math.pi/2
    radius=27.25 if candidate=='fallback2' else 23.75
    lane=-2 if candidate=='fallback2' else -1
    speed=6.5 if candidate=='fallback1' else 3 if candidate=='fallback3' else 8
    for i,row in enumerate(rows):
        t=(i+1)/20
        distance=min(12,speed*t) if candidate=='fallback3' else speed*t
        angle=start+direction*distance/radius
        if (row.get('frame')!=i or abs(row.get('time_s',-1)-t)>1e-6 or
                row.get('case')!=case or row.get('candidate_id')!=candidate or
                row.get('lane_id')!=lane or row.get('requested_radius_m')!=radius or
                abs(row.get('ego_x_m',1e9)-radius*math.cos(angle))>1e-5 or
                abs(row.get('ego_y_m',1e9)-radius*math.sin(angle))>1e-5 or
                row.get('ego_speed_mps')!=(0 if candidate=='fallback3' and speed*t>12 else speed)):
            raise ValueError('Rotary requested track differs')
    return {'format':'c234827-copied-runner-cpu-check-v1',
            'case_id':config['case_id'],'candidate_id':candidate,
            'requested_frames':240,'carla_imported':False,
            'physical_island_verified':False,'delivery_ready':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true',required=True)
    parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(check(args.bundle)))
