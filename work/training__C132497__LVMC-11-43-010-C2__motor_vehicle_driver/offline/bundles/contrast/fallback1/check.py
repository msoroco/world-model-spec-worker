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
        cfg.get('complete_circle_xml_geometry_authored') is not True or
        cfg.get('circulation_direction')!='counterclockwise' or
        cfg.get('right_lane_outer') is not True or
        cfg.get('original_native_observed') is not False or
        cfg.get('actual_exit_observed') is not False or
        cfg.get('physical_roundabout_verified') is not False):
        raise ValueError('C132497 source scope differs')
    for key,name in (('road_sha256','right-exit-road.xodr'),
        ('tracks_sha256','requested-tracks.jsonl'),
        ('controller_intention_sha256','controller-intention.json'),
        ('assignment_sha256','assignment-source.json'),
        ('case_plan_sha256','case-plan.json')):
        if cfg.get(key)!=sha(bundle/name):raise ValueError('C132497 source hash differs')
    intention=json.loads((bundle/'controller-intention.json').read_text())
    if (intention.get('format')!='c132497-predeclared-controller-intention-v1' or
        intention.get('case_id')!=cfg['case_id'] or
        intention.get('candidate_id')!=candidate or
        intention.get('source_kind')!='authored_controller_route_before_motion' or
        intention.get('route_road_ids')!=[20,21,22] or
        intention.get('circulating_loop_road_ids')!=[21,23] or
        intention.get('intended_exit_road_id')!=22 or
        intention.get('turn_direction')!='right' or
        intention.get('actual_exit_observed') is not False or
        intention.get('legal_verdict') is not None):
        raise ValueError('C132497 predeclared controller intention differs')
    lane,radius,offset=(-2,20.25,5.25) if witness=='reference' else (-1,16.75,1.75)
    speed,camera,dwell={'primary':(8,'standard',0.0),
        'fallback1':(6.5,'standard',0.0),
        'fallback2':(8,'elevated_overview',0.0),
        'fallback3':(8,'standard',2.0)}[candidate]
    if (cfg.get('requested_lane_id')!=lane or
        cfg.get('requested_arc_radius_m')!=radius or
        cfg.get('requested_speed_mps')!=speed or
        cfg.get('camera_policy')!=camera or
        cfg.get('pre_entry_dwell_s')!=dwell):
        raise ValueError('C132497 candidate policy differs')
    document=ET.parse(bundle/'right-exit-road.xodr').getroot()
    road={int(x.attrib['id']):x for x in document.findall('road')}
    if set(road)!={20,21,22,23}:raise ValueError('C132497 closed roundabout roads differ')
    for ident,previous,next_ in ((20,None,100),(21,100,101),
                                  (22,101,None),(23,101,100)):
        node=road[ident]
        if {int(x.attrib['id']):x.attrib['type'] for x in node.findall('./lanes/laneSection/right/lane')}!={-1:'driving',-2:'driving'}:
            raise ValueError('C132497 lane IDs differ')
        for tag,target in (('predecessor',previous),('successor',next_)):
            link=node.find('./link/'+tag)
            if ((link is None)!=(target is None) or
                (target is not None and (link.attrib['elementType']!='junction' or
                                         int(link.attrib['elementId'])!=target))):
                raise ValueError('C132497 road link differs')
    junctions={int(x.attrib['id']):x for x in document.findall('junction')}
    if set(junctions)!={100,101}:raise ValueError('C132497 roundabout junctions differ')
    expected={100:{(20,21),(23,21)},101:{(21,22),(21,23)}}
    for ident,connections in expected.items():
        actual=set()
        for connection in junctions[ident].findall('connection'):
            pair=(int(connection.attrib['incomingRoad']),int(connection.attrib['connectingRoad']))
            if (connection.attrib.get('contactPoint')!='start' or
                {(int(x.attrib['from']),int(x.attrib['to'])) for x in connection.findall('laneLink')}
                    != {(-1,-1),(-2,-2)}):
                raise ValueError('C132497 roundabout lane connection differs')
            actual.add(pair)
        if actual!=connections:raise ValueError('C132497 roundabout topology differs')
    for ident,length,x,y,heading in ((21,15*math.pi/2,22,-15,0),
                                      (23,45*math.pi/2,37,0,math.pi/2)):
        geometry=road[ident].find('./planView/geometry')
        arc=geometry.find('arc')
        if (arc is None or abs(float(arc.attrib['curvature'])-1/15)>1e-9 or
            abs(float(geometry.attrib['length'])-length)>1e-8 or
            abs(float(geometry.attrib['x'])-x)>1e-8 or
            abs(float(geometry.attrib['y'])-y)>1e-8 or
            abs(float(geometry.attrib['hdg'])-heading)>1e-8):
            raise ValueError('C132497 counterclockwise circle arc differs')
    for ident,first,second in ((20,(0,10,-46,math.pi/2,19,None),
                                 (19,10,-27,math.pi/2,12*math.pi/2,-1/12)),
                               (22,(0,37,0,math.pi/2,12*math.pi/2,-1/12),
                                 (12*math.pi/2,49,12,0,30,None))):
        geometries=road[ident].findall('./planView/geometry')
        if len(geometries)!=2:
            raise ValueError('C132497 first-exit connector geometry differs')
        for geometry,values in zip(geometries,(first,second)):
            expected_s,expected_x,expected_y,expected_h,expected_len,expected_k=values
            actual=(float(geometry.attrib[k]) for k in ('s','x','y','hdg','length'))
            if any(abs(a-b)>1e-8 for a,b in zip(actual,
                    (expected_s,expected_x,expected_y,expected_h,expected_len))):
                raise ValueError('C132497 first-exit connector coordinates differ')
            arc=geometry.find('arc')
            if (expected_k is None and geometry.find('line') is None or
                expected_k is not None and (arc is None or
                    abs(float(arc.attrib['curvature'])-expected_k)>1e-9)):
                raise ValueError('C132497 first-exit connector curvature differs')
    if any(road[ident].attrib['junction']!=str(junction) for ident,junction in
           ((20,-1),(21,100),(22,101),(23,101))):
        raise ValueError('C132497 junction membership differs')
    track=rows(bundle/'requested-tracks.jsonl')
    if len(track)!=240:raise ValueError('C132497 track coverage differs')
    phases=set()
    for i,row in enumerate(track):
        t=(i+1)/20;distance=speed*max(0,t-dwell)
        connector=12-offset;first=19+connector*math.pi/2
        second=first+radius*math.pi/2
        if distance<19:
            phase='entry';road_id=20;x=10+offset;y=-46+distance;heading=90
        elif distance<first:
            phase='entry';road_id=20;theta=math.pi-(distance-19)/connector
            x=22+connector*math.cos(theta);y=-27+connector*math.sin(theta)
            heading=math.degrees(theta-math.pi/2)
        elif distance<second:
            phase='circulation';road_id=21
            theta=-math.pi/2+(distance-first)/radius
            x=22+radius*math.cos(theta);y=radius*math.sin(theta)
            heading=math.degrees(theta+math.pi/2)
        else:
            phase='exit';road_id=22;after=distance-second
            if after<connector*math.pi/2:
                theta=math.pi-after/connector
                x=49+connector*math.cos(theta);y=connector*math.sin(theta)
                heading=math.degrees(theta-math.pi/2)
            else:
                x=49+after-connector*math.pi/2;y=connector;heading=0
        if (row.get('frame')!=i or row.get('time_s')!=t or
            row.get('source_kind')!='authored_native_request' or
            row.get('witness')!=witness or row.get('candidate_id')!=candidate or
            row.get('phase')!=phase or row.get('road_id')!=road_id or
            row.get('lane_id')!=lane or
            abs(row.get('ego_x_m',1e9)-x)>1e-5 or
            abs(row.get('ego_y_m',1e9)-y)>1e-5 or
            abs(row.get('ego_heading_deg',1e9)-heading)>1e-5 or
            row.get('ego_speed_mps')!=(0 if t<=dwell else speed) or
            row.get('intended_exit_kind')!='right_turn' or
            row.get('actual_exit_observed') is not False or
            row.get('physical_roundabout_verified') is not False):
            raise ValueError(f'C132497 requested frame differs: {i}')
        phases.add(phase)
    if phases!={'entry','circulation','exit'}:
        raise ValueError('C132497 authored phases differ')
    return {'format':'c132497-exact-cpu-check-v1','case_id':cfg['case_id'],
        'candidate_id':candidate,'requested_frames':240,'phases':sorted(phases),
        'complete_circle_xml_geometry_authored':True,
        'physical_roundabout_verified':False,'actual_exit_observed':False,
        'delivery_ready':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    print(json.dumps(check(p.parse_args().bundle)))
