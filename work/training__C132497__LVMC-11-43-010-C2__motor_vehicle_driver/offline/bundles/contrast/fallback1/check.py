"""Independent exact CPU check for copied C132497 right-exit requests."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

LAW='The following regulations pertain to the operation of vehicles within a roundabout: The operator of a vehicle who intends to exit a roundabout: Shall use the right lane to turn right.'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def check(bundle):
    bundle=Path(bundle);cfg=json.loads((bundle/'config.json').read_text())
    assignment=json.loads((bundle/'assignment-source.json').read_text())
    plan=json.loads((bundle/'case-plan.json').read_text())
    witness=cfg.get('case_id','').removeprefix(cfg.get('assignment_id','')+'__')
    candidate=cfg.get('candidate_id')
    if (cfg.get('format')!='c132497-right-exit-request-v1' or
        assignment.get('assignment_id')!=cfg.get('assignment_id') or
        assignment['law_record']['text']!=LAW or
        plan.get('assignment_id')!=cfg.get('assignment_id') or
        plan.get('source_law_text')!=LAW or
        cfg.get('case_id') not in {x['case_id'] for x in plan['cases']} or
        witness not in ('reference','contrast') or
        candidate not in ('primary','fallback1','fallback2','fallback3') or
        cfg.get('law_id')!='LVMC-11-43-010-C2' or
        cfg.get('cell_id')!='C132497' or
        cfg.get('actor')!='motor_vehicle_driver' or
        cfg.get('rate_hz')!=20 or cfg.get('frames')!=240 or
        cfg.get('status')!='unselected_native_request' or
        cfg.get('connected_right_exit_authored') is not True or
        cfg.get('original_native_observed') is not False or
        cfg.get('actual_exit_observed') is not False or
        cfg.get('physical_roundabout_verified') is not False):
        raise ValueError('C132497 source scope differs')
    for key,name in (('road_sha256','right-exit-road.xodr'),
        ('tracks_sha256','requested-tracks.jsonl'),
        ('assignment_sha256','assignment-source.json'),
        ('case_plan_sha256','case-plan.json')):
        if cfg.get(key)!=sha(bundle/name):raise ValueError('C132497 source hash differs')
    lane,radius=(-2,16.75) if witness=='reference' else (-1,20.25)
    speed,camera,stop={'primary':(8,'standard',None),
        'fallback1':(6.5,'standard',None),
        'fallback2':(8,'elevated_overview',None),
        'fallback3':(3,'standard',12)}[candidate]
    if (cfg.get('requested_lane_id')!=lane or
        cfg.get('requested_arc_radius_m')!=radius or
        cfg.get('requested_speed_mps')!=speed or
        cfg.get('camera_policy')!=camera or
        cfg.get('stop_distance_m')!=stop):
        raise ValueError('C132497 candidate policy differs')
    road={int(x.attrib['id']):x for x in ET.parse(bundle/'right-exit-road.xodr').getroot().findall('road')}
    if set(road)!={20,21,22}:raise ValueError('C132497 road IDs differ')
    for ident,previous,next_ in ((20,None,21),(21,20,22),(22,21,None)):
        node=road[ident]
        if {int(x.attrib['id']):x.attrib['type'] for x in node.findall('./lanes/laneSection/right/lane')}!={-1:'driving',-2:'driving'}:
            raise ValueError('C132497 lane IDs differ')
        for tag,target in (('predecessor',previous),('successor',next_)):
            link=node.find('./link/'+tag)
            if (link is None)!=(target is None) or (target is not None and int(link.attrib['elementId'])!=target):
                raise ValueError('C132497 road link differs')
    arc=road[21].find('./planView/geometry/arc')
    if abs(float(arc.attrib['curvature'])+1/22)>1e-9:
        raise ValueError('C132497 clockwise arc differs')
    track=rows(bundle/'requested-tracks.jsonl')
    if len(track)!=240:raise ValueError('C132497 track coverage differs')
    phases=set()
    for i,row in enumerate(track):
        t=(i+1)/20;distance=speed*t if stop is None else min(stop,speed*t)
        if distance<30:
            phase='entry';road_id=20;x=22-radius;y=-52+distance;heading=90
        elif distance<30+radius*math.pi/2:
            phase='circulation';road_id=21
            theta=math.pi-(distance-30)/radius
            x=22+radius*math.cos(theta);y=-22+radius*math.sin(theta)
            heading=math.degrees(theta-math.pi/2)
        else:
            phase='exit';road_id=22;x=22+distance-30-radius*math.pi/2
            y=-22+radius;heading=0
        if (row.get('frame')!=i or row.get('time_s')!=t or
            row.get('source_kind')!='authored_native_request' or
            row.get('witness')!=witness or row.get('candidate_id')!=candidate or
            row.get('phase')!=phase or row.get('road_id')!=road_id or
            row.get('lane_id')!=lane or
            abs(row.get('ego_x_m',1e9)-x)>1e-5 or
            abs(row.get('ego_y_m',1e9)-y)>1e-5 or
            abs(row.get('ego_heading_deg',1e9)-heading)>1e-5 or
            row.get('ego_speed_mps')!=(0 if stop is not None and speed*t>stop else speed) or
            row.get('intended_exit_kind')!='right_turn' or
            row.get('actual_exit_observed') is not False or
            row.get('physical_roundabout_verified') is not False):
            raise ValueError(f'C132497 requested frame differs: {i}')
        phases.add(phase)
    if phases!=({'entry'} if stop is not None else {'entry','circulation','exit'}):
        raise ValueError('C132497 authored phases differ')
    return {'format':'c132497-exact-cpu-check-v1','case_id':cfg['case_id'],
        'candidate_id':candidate,'requested_frames':240,'phases':sorted(phases),
        'physical_roundabout_verified':False,'actual_exit_observed':False,
        'delivery_ready':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    print(json.dumps(check(p.parse_args().bundle)))
