"""Independently audit the closed roundabout and 1,920 authored request rows."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
ROOT=CASE.parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]

def audit():
    assignment=ROOT/'inputs'/CASE.name/'assignment.json'
    source=json.loads(assignment.read_text())
    if (source['law_record']['text']!=
        'The following regulations pertain to the operation of vehicles within a roundabout: The operator of a vehicle who intends to exit a roundabout: Shall use the right lane to turn right.' or
        source['local_snapshot']['memberships']['full-train']):
        raise ValueError('C132497 exact law or accepted membership differs')
    road_path=HERE/'right-exit-road.xodr'
    document=ET.parse(road_path).getroot()
    road={int(x.attrib['id']):x for x in document.findall('road')}
    if set(road)!={20,21,22,23}:raise ValueError('C132497 complete-circle road inventory differs')
    # Explicit endpoints and tangent continuity of entry, both clockwise arcs, and exit.
    start=road[20].find('./planView/geometry');arc=road[21].find('./planView/geometry')
    exit_=road[22].find('./planView/geometry');remainder=road[23].find('./planView/geometry')
    entry_end=(float(start.attrib['x'])+30*math.cos(float(start.attrib['hdg'])),
               float(start.attrib['y'])+30*math.sin(float(start.attrib['hdg'])))
    curvature=float(arc.find('arc').attrib['curvature'])
    arc_length=float(arc.attrib['length'])
    center=(float(arc.attrib['x'])-math.sin(float(arc.attrib['hdg']))/curvature,
            float(arc.attrib['y'])+math.cos(float(arc.attrib['hdg']))/curvature)
    angle=float(arc.attrib['hdg'])+curvature*arc_length
    arc_end=(center[0]+math.sin(angle)/curvature,
             center[1]-math.cos(angle)/curvature)
    remainder_curvature=float(remainder.find('arc').attrib['curvature'])
    remainder_length=float(remainder.attrib['length'])
    remainder_center=(float(remainder.attrib['x'])-
                      math.sin(float(remainder.attrib['hdg']))/remainder_curvature,
                      float(remainder.attrib['y'])+
                      math.cos(float(remainder.attrib['hdg']))/remainder_curvature)
    remainder_angle=float(remainder.attrib['hdg'])+remainder_curvature*remainder_length
    remainder_end=(remainder_center[0]+math.sin(remainder_angle)/remainder_curvature,
                   remainder_center[1]-math.cos(remainder_angle)/remainder_curvature)
    if (math.hypot(entry_end[0]-float(arc.attrib['x']),
        entry_end[1]-float(arc.attrib['y']))>1e-7 or
        math.hypot(arc_end[0]-float(exit_.attrib['x']),
        arc_end[1]-float(exit_.attrib['y']))>1e-7 or
        math.hypot(arc_end[0]-float(remainder.attrib['x']),
        arc_end[1]-float(remainder.attrib['y']))>1e-7 or
        math.hypot(remainder_end[0]-float(arc.attrib['x']),
        remainder_end[1]-float(arc.attrib['y']))>1e-7 or
        abs(angle)>1e-7 or
        abs(float(exit_.attrib['hdg']))>1e-7 or
        abs(remainder_angle+3*math.pi/2)>1e-7 or
        abs(curvature+1/22)>1e-9 or
        abs(remainder_curvature+1/22)>1e-9 or
        abs(arc_length+remainder_length-44*math.pi)>1e-8):
        raise ValueError('C132497 circle closure or route tangent differs')
    junctions={int(x.attrib['id']):x for x in document.findall('junction')}
    expected={100:{(20,21),(23,21)},101:{(21,22),(21,23)}}
    if set(junctions)!=set(expected):raise ValueError('C132497 junction inventory differs')
    for ident,pairs in expected.items():
        actual=set()
        for connection in junctions[ident].findall('connection'):
            actual.add((int(connection.attrib['incomingRoad']),
                        int(connection.attrib['connectingRoad'])))
            if {(int(link.attrib['from']),int(link.attrib['to']))
                for link in connection.findall('laneLink')}!={(-1,-1),(-2,-2)}:
                raise ValueError('C132497 junction lane allocation differs')
        if actual!=pairs:raise ValueError('C132497 junction topology differs')
    manifest=json.loads((HERE/'manifest.json').read_text())
    if len(manifest['entries'])!=8 or manifest['road_sha256']!=sha(road_path):
        raise ValueError('C132497 construction manifest differs')
    checked=0;exit_requests=0
    for item in manifest['entries']:
        witness=item['case_id'].removeprefix(CASE.name+'__');candidate=item['candidate_id']
        folder=HERE/'drafts'/witness/candidate
        config=json.loads((folder/'config.json').read_text())
        track=rows(folder/'requested-tracks.jsonl')
        if (len(track)!=240 or item['config_sha256']!=sha(folder/'config.json') or
            item['tracks_sha256']!=sha(folder/'requested-tracks.jsonl') or
            item['controller_intention_sha256']!=sha(folder/'controller-intention.json') or
            config['controller_intention_sha256']!=sha(folder/'controller-intention.json') or
            config['assignment_sha256']!=sha(assignment) or
            config['road_sha256']!=sha(road_path)):
            raise ValueError('C132497 construction source hashes differ')
        road_sequence=[x['road_id'] for x in track]
        if road_sequence!=sorted(road_sequence):
            raise ValueError('C132497 requested phase order reverses')
        if set(road_sequence)!={20,21,22}:
            raise ValueError('C132497 authored exit request incomplete')
        if candidate=='fallback3' and (any(track[i]['ego_speed_mps']!=0 for i in range(40)) or
            track[40]['ego_speed_mps']<=0):
            raise ValueError('C132497 dwell fallback timing differs')
        exit_requests+=22 in road_sequence;checked+=len(track)
    result={'format':'c132497-independent-construction-audit-v1',
        'road_sha256':sha(road_path),'request_rows_checked':checked,
        'authored_exit_requests':exit_requests,
        'complete_circle_xml_geometry_authored':True,
        'original_native_observed':False,
        'delivery_ready':False}
    (HERE/'construction-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
