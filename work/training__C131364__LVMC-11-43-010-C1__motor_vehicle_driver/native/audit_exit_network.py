"""Independently verify the authored connected left-exit geometry and routes."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
ROOT=CASE.parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def audit():
    road=HERE/'left-exit-road.xodr'
    manifest_path=HERE/'exit-network-drafts'/'manifest.json'
    assignment=ROOT/'inputs'/CASE.name/'assignment.json'
    plan=CASE/'case-plan.json'
    manifest=json.loads(manifest_path.read_text())
    if (manifest['format']!='c131364-connected-exit-construction-v1' or
        manifest['assignment_id']!=CASE.name or
        manifest['assignment_sha256']!=sha(assignment) or
        manifest['case_plan_sha256']!=sha(plan) or
        manifest['road_sha256']!=sha(road) or
        manifest['original_native_observed'] or manifest['physical_roundabout_verified'] or
        manifest['delivery_ready']):
        raise ValueError('C131364 connected network provenance differs')
    xml=ET.parse(road).getroot()
    roads={int(node.attrib['id']):node for node in xml.findall('road')}
    if set(roads)!={10,11,12}:raise ValueError('C131364 entry/arc/exit roads missing')
    endpoints={10:((-30,-22,0),(0,-22,0)),
               11:((0,-22,0),(22,0,math.pi/2)),
               12:((22,0,math.pi/2),(22,30,math.pi/2))}
    for ident,road_node in roads.items():
        g=road_node.find('./planView/geometry')
        length=float(road_node.attrib['length'])
        x,y,h=(float(g.attrib[k]) for k in ('x','y','hdg'))
        if ident==11:
            k=float(g.find('arc').attrib['curvature'])
            end=(x+(math.sin(h+k*length)-math.sin(h))/k,
                 y-(math.cos(h+k*length)-math.cos(h))/k,h+k*length)
            if abs(k-1/22)>1e-9 or abs(length-11*math.pi)>1e-8:
                raise ValueError('C131364 circulatory arc differs')
        else:
            if g.find('line') is None:raise ValueError('C131364 approach/exit line absent')
            end=(x+length*math.cos(h),y+length*math.sin(h),h)
        for observed,expected in ((x,endpoints[ident][0][0]),
                                  (y,endpoints[ident][0][1]),
                                  (h,endpoints[ident][0][2]),
                                  *zip(end,endpoints[ident][1])):
            if abs(observed-expected)>1e-7:
                raise ValueError(f'C131364 road {ident} endpoint differs')
        expected_predecessor={10:None,11:10,12:11}[ident]
        expected_successor={10:11,11:12,12:None}[ident]
        for relation,target in (('predecessor',expected_predecessor),
                                ('successor',expected_successor)):
            link=road_node.find('./link/'+relation)
            if (link is None)!=(target is None):
                raise ValueError('C131364 road link coverage differs')
            if target is not None and int(link.attrib['elementId'])!=target:
                raise ValueError('C131364 road link target differs')
        lanes={int(node.attrib['id']):node for node in road_node.findall('./lanes/laneSection/right/lane')}
        if set(lanes)!={-1,-2}:raise ValueError('C131364 two driving lanes missing')
        for lane_id,node in lanes.items():
            if node.attrib['type']!='driving' or float(node.find('width').attrib['a'])!=3.5:
                raise ValueError('C131364 lane width/type differs')
            for relation,target in (('predecessor',expected_predecessor),
                                    ('successor',expected_successor)):
                lane_link=node.find('./link/'+relation)
                if (lane_link is None)!=(target is None):
                    raise ValueError('C131364 lane link coverage differs')
                if target is not None and int(lane_link.attrib['id'])!=lane_id:
                    raise ValueError('C131364 lane link identity differs')
    expected={(w,c) for w in ('witness_1','witness_2')
              for c in ('primary','fallback1','fallback2','fallback3')}
    seen=set();rows_checked=0;complete_exit_paths=0
    for item in manifest['entries']:
        witness=item['case_id'].removeprefix(CASE.name+'__')
        candidate=item['candidate_id']
        if (witness,candidate) not in expected or (witness,candidate) in seen:
            raise ValueError('C131364 connected candidate coverage differs')
        seen.add((witness,candidate))
        folder=HERE/'exit-network-drafts'/witness/candidate
        config_path=folder/'config.json';track=folder/'requested-tracks.jsonl'
        config=json.loads(config_path.read_text())
        if (item['config_sha256']!=sha(config_path) or item['tracks_sha256']!=sha(track) or
            config['road_sha256']!=sha(road) or config['tracks_sha256']!=sha(track) or
            config['assignment_sha256']!=sha(assignment) or
            config['case_plan_sha256']!=sha(plan) or
            not config['connected_exit_authored'] or config['actual_exit_observed'] or
            config['original_native_observed'] or config['roundabout_verified']):
            raise ValueError('C131364 connected config differs')
        lane,radius=(-1,23.75) if witness=='witness_1' else (-2,27.25)
        speed=6.5 if candidate=='fallback1' else 3 if candidate=='fallback3' else 8
        rows=[json.loads(line) for line in track.read_text().splitlines()]
        if len(rows)!=240:raise ValueError('C131364 connected route frame coverage differs')
        phases=set()
        previous=None
        for i,row in enumerate(rows):
            time_s=(i+1)/20
            travel=min(12,speed*time_s) if candidate=='fallback3' else speed*time_s
            if travel<30:
                phase='entry';x=-30+travel;y=-radius;heading=0;road_id=10
            elif travel<30+radius*math.pi/2:
                phase='circulation';theta=-math.pi/2+(travel-30)/radius
                x=radius*math.cos(theta);y=radius*math.sin(theta)
                heading=math.degrees(theta+math.pi/2);road_id=11
            else:
                phase='exit';x=radius;y=travel-30-radius*math.pi/2
                heading=90;road_id=12
            if (row['frame']!=i or abs(row['time_s']-time_s)>1e-6 or
                row['phase']!=phase or row['road_id']!=road_id or row['lane_id']!=lane or
                abs(row['ego_x_m']-x)>1e-5 or abs(row['ego_y_m']-y)>1e-5 or
                abs(row['ego_heading_deg']-heading)>1e-5 or
                row['actual_exit_observed'] or row['roundabout_verified']):
                raise ValueError(f'C131364 connected route row differs at {i}')
            if previous is not None:
                step=math.hypot(row['ego_x_m']-previous[0],row['ego_y_m']-previous[1])
                if step>.41:raise ValueError('C131364 connected route jump')
            previous=(row['ego_x_m'],row['ego_y_m'])
            phases.add(phase);rows_checked+=1
        if sorted(phases)!=item['phases']:
            raise ValueError('C131364 connected phase receipt differs')
        if candidate!='fallback3':
            if phases!={'entry','circulation','exit'}:
                raise ValueError('C131364 left exit not requested')
            complete_exit_paths+=1
        elif phases!={'entry'}:
            raise ValueError('C131364 stop fallback crossed into circulatory road')
    if seen!=expected or rows_checked!=1920 or complete_exit_paths!=6:
        raise ValueError('C131364 connected network incomplete')
    result={'format':'c131364-independent-connected-exit-audit-v1',
            'manifest_sha256':sha(manifest_path),'roads_checked':3,
            'lane_links_checked':12,'requested_rows_checked':rows_checked,
            'complete_authored_exit_paths':complete_exit_paths,
            'original_native_observed':False,'physical_roundabout_verified':False,
            'delivery_ready':False}
    (HERE/'exit-network-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
