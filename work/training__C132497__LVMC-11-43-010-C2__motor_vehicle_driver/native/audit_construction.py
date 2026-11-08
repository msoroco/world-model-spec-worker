"""Independently audit the clockwise right-exit road and 1,920 authored request rows."""
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
    road={int(x.attrib['id']):x for x in ET.parse(road_path).getroot().findall('road')}
    if set(road)!={20,21,22}:raise ValueError('C132497 road inventory differs')
    # Explicit endpoints and tangent continuity of south entry, clockwise arc, east exit.
    start=road[20].find('./planView/geometry');arc=road[21].find('./planView/geometry')
    exit_=road[22].find('./planView/geometry')
    entry_end=(float(start.attrib['x'])+30*math.cos(float(start.attrib['hdg'])),
               float(start.attrib['y'])+30*math.sin(float(start.attrib['hdg'])))
    curvature=float(arc.find('arc').attrib['curvature'])
    arc_length=float(arc.attrib['length'])
    center=(float(arc.attrib['x'])-math.sin(float(arc.attrib['hdg']))/curvature,
            float(arc.attrib['y'])+math.cos(float(arc.attrib['hdg']))/curvature)
    angle=float(arc.attrib['hdg'])+curvature*arc_length
    arc_end=(center[0]+math.sin(angle)/curvature,
             center[1]-math.cos(angle)/curvature)
    if (math.hypot(entry_end[0]-float(arc.attrib['x']),
        entry_end[1]-float(arc.attrib['y']))>1e-7 or
        math.hypot(arc_end[0]-float(exit_.attrib['x']),
        arc_end[1]-float(exit_.attrib['y']))>1e-7 or
        abs(angle)>1e-7 or
        abs(float(exit_.attrib['hdg']))>1e-7):
        raise ValueError('C132497 connected endpoints or headings differ')
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
            config['assignment_sha256']!=sha(assignment) or
            config['road_sha256']!=sha(road_path)):
            raise ValueError('C132497 construction source hashes differ')
        road_sequence=[x['road_id'] for x in track]
        if road_sequence!=sorted(road_sequence):
            raise ValueError('C132497 requested phase order reverses')
        if candidate=='fallback3':
            if set(road_sequence)!={20}:raise ValueError('C132497 stop request entered arc')
        elif set(road_sequence)!={20,21,22}:
            raise ValueError('C132497 authored exit request incomplete')
        exit_requests+=22 in road_sequence;checked+=len(track)
    result={'format':'c132497-independent-construction-audit-v1',
        'road_sha256':sha(road_path),'request_rows_checked':checked,
        'authored_exit_requests':exit_requests,'original_native_observed':False,
        'delivery_ready':False}
    (HERE/'construction-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
