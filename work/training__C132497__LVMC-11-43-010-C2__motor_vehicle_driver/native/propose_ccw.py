"""Author the first-exit counterclockwise route used by unselected CPU bundles."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
FPS=20
FRAMES=240
LANE_OFFSETS={'reference':(-2,5.25),'contrast':(-1,1.75)}
POLICIES={'primary':(8.0,0.0),'fallback1':(6.5,0.0),
          'fallback2':(8.0,0.0),'fallback3':(8.0,2.0)}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def segment(parent,s,x,y,heading,length,curvature=None):
    geom=ET.SubElement(parent,'geometry',s=str(s),x=str(x),y=str(y),
                       hdg=str(heading),length=str(length))
    ET.SubElement(geom,'line' if curvature is None else 'arc',
                  **({} if curvature is None else {'curvature':str(curvature)}))

def road(root,ident,name,length,previous,next_,junction,segments):
    node=ET.SubElement(root,'road',id=str(ident),name=name,
                       length=str(length),junction=str(junction))
    link=ET.SubElement(node,'link')
    for tag,value in (('predecessor',previous),('successor',next_)):
        if value is not None:ET.SubElement(link,tag,elementType='junction',elementId=str(value))
    view=ET.SubElement(node,'planView')
    for values in segments:segment(view,*values)
    lanes=ET.SubElement(node,'lanes')
    ET.SubElement(lanes,'laneOffset',s='0',a='0',b='0',c='0',d='0')
    section=ET.SubElement(lanes,'laneSection',s='0')
    ET.SubElement(section,'left')
    center=ET.SubElement(section,'center')
    ET.SubElement(center,'lane',id='0',type='none',level='false')
    right=ET.SubElement(section,'right')
    for lane_id in (-1,-2):
        lane=ET.SubElement(right,'lane',id=str(lane_id),type='driving',level='false')
        lane_link=ET.SubElement(lane,'link')
        if previous is not None:ET.SubElement(lane_link,'predecessor',id=str(lane_id))
        if next_ is not None:ET.SubElement(lane_link,'successor',id=str(lane_id))
        ET.SubElement(lane,'width',sOffset='0',a='3.5',b='0',c='0',d='0')
        ET.SubElement(lane,'roadMark',sOffset='0',type='broken',color='white',width='0.12')
    ET.SubElement(node,'objects');ET.SubElement(node,'signals')

def junction(root,ident,name,connections):
    node=ET.SubElement(root,'junction',id=str(ident),name=name)
    for number,(incoming,connecting) in enumerate(connections):
        connection=ET.SubElement(node,'connection',id=str(number),
            incomingRoad=str(incoming),connectingRoad=str(connecting),contactPoint='start')
        for lane in (-1,-2):
            ET.SubElement(connection,'laneLink',**{'from':str(lane),'to':str(lane)})

def open_drive():
    root=ET.Element('OpenDRIVE')
    ET.SubElement(root,'header',revMajor='1',revMinor='4',
        name='C132497-counterclockwise-first-exit-draft',version='1.00',
        date='2026-11-11',north='60',south='-60',east='90',west='-20',vendor='worker')
    turn=12*math.pi/2
    road(root,20,'south entry and right merge',19+turn,None,100,-1,
         [(0,10,-46,math.pi/2,19,None),(19,10,-27,math.pi/2,turn,-1/12)])
    road(root,21,'counterclockwise first-exit quarter',15*math.pi/2,100,101,100,
         [(0,22,-15,0,15*math.pi/2,1/15)])
    road(root,22,'east right-exit connector',turn+30,101,None,101,
         [(0,37,0,math.pi/2,turn,-1/12),(turn,49,12,0,30,None)])
    road(root,23,'counterclockwise remaining loop',45*math.pi/2,101,100,101,
         [(0,37,0,math.pi/2,45*math.pi/2,1/15)])
    junction(root,100,'south-entry-merge',[(20,21),(23,21)])
    junction(root,101,'east-first-exit-split',[(21,22),(21,23)])
    return ET.tostring(root,encoding='unicode')+'\n'

def position(distance,offset):
    connector=12-offset
    circle=15+offset
    first=19+connector*math.pi/2
    second=first+circle*math.pi/2
    if distance<19:
        return 20,'entry',10+offset,-46+distance,90
    if distance<first:
        theta=math.pi-(distance-19)/connector
        return 20,'entry',22+connector*math.cos(theta),-27+connector*math.sin(theta),math.degrees(theta-math.pi/2)
    if distance<second:
        theta=-math.pi/2+(distance-first)/circle
        return 21,'circulation',22+circle*math.cos(theta),circle*math.sin(theta),math.degrees(theta+math.pi/2)
    after=distance-second
    if after<connector*math.pi/2:
        theta=math.pi-after/connector
        return 22,'exit',49+connector*math.cos(theta),connector*math.sin(theta),math.degrees(theta-math.pi/2)
    return 22,'exit',49+after-connector*math.pi/2,connector,0

def build():
    law=ROOT/'inputs/coverage/branch-sources.json'
    source=json.loads(law.read_text())
    selected=source['laws'] if 'laws' in source else source
    a=selected['LVMC-11-43-010-A']['law']['text']
    c2=selected['LVMC-11-43-010-C2']['law']['text']
    if ('counterclockwise direction' not in a or 'right lane to turn right' not in c2):
        raise ValueError('Frozen roundabout direction or right-exit source differs')
    road_path=HERE/'ccw-right-exit-draft.xodr';road_path.write_text(open_drive())
    document=ET.parse(road_path).getroot()
    if ({int(x.attrib['id']) for x in document.findall('road')}!={20,21,22,23} or
        {int(x.attrib['id']) for x in document.findall('junction')}!={100,101}):
        raise ValueError('CCW design road/junction inventory differs')
    cases=[]
    for witness,(lane,offset) in LANE_OFFSETS.items():
        for candidate,(speed,dwell) in POLICIES.items():
            route=[]
            for i in range(FRAMES):
                d=speed*max(0,(i+1)/FPS-dwell)
                road_id,phase,x,y,heading=position(d,offset)
                route.append((road_id,phase,x,y,heading))
            if ({row[1] for row in route}!={'entry','circulation','exit'} or
                route[-1][0]!=22 or route[-1][2]<=49 or
                (candidate=='fallback3' and any(position(0,offset)!=row for row in route[:40]))):
                raise ValueError('CCW candidate does not complete first right exit')
            cases.append({'witness':witness,'candidate_id':candidate,'lane_id':lane,
                          'circulating_radius_m':15+offset,'connector_radius_m':12-offset,
                          'first_frame_road_id':route[0][0],
                          'last_frame_road_id':route[-1][0],
                          'last_frame_x_m':round(route[-1][2],5),
                          'last_frame_y_m':round(route[-1][3],5),
                          'last_frame_heading_deg':route[-1][4],
                          'circulation_frames':sum(row[1]=='circulation' for row in route),
                          'exit_frames':sum(row[1]=='exit' for row in route)})
    if (LANE_OFFSETS['reference'][1]<=LANE_OFFSETS['contrast'][1] or
        15+LANE_OFFSETS['reference'][1]<=15+LANE_OFFSETS['contrast'][1]):
        raise ValueError('Reference right lane is not outer on CCW circle')
    proof={'format':'c132497-counterclockwise-first-exit-design-v1',
           'status':'integrated_unselected_cpu_draft','passed':True,
           'frozen_branch_sources_sha256':sha(law),
           'source_direction_text':a,'source_right_exit_text':c2,
           'road_sha256':sha(road_path),'cases':cases,
           'reference_right_lane_outer':True,
           'current_bundles_replaced':True,
           'native_map_verified':False,'original_native_observed':False,
           'delivery_ready':False}
    path=HERE/'ccw-right-exit-draft-proof.json'
    path.write_text(json.dumps(proof,indent=2)+'\n')
    return proof

if __name__=='__main__':
    proof=build()
    print(json.dumps({'passed':True,'integrated_unselected_cpu_draft':True,
                      'cases':len(proof['cases']),'road_sha256':proof['road_sha256']}))
