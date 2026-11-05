"""C382355 right-only-lane turn/straight pair; CPU geometry, not Native proof."""
from __future__ import annotations

import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

LANE_WIDTH_M=3.5
CASE_APPROACH_Y_M={'controlled_1':-5.25,'controlled_2':-5.25}


def open_drive():
    root=ET.Element('OpenDRIVE')
    ET.SubElement(root,'header',revMajor='1',revMinor='4',name='C382355-right-only-lane-turn-straight-draft',
                  version='1',date='2026-11-05',north='100',south='-100',east='100',west='-100',
                  vendor='full-train-worker')
    roads=((1,-100,0,0,93,-1),(2,7,0,0,93,-1),
           (3,0,100,-math.pi/2,93,-1),(4,0,-7,-math.pi/2,93,-1),
           (13,-7,0,0,7*math.pi/2,100),(14,-7,0,0,14,100))
    for ident,x,y,heading,length,junction in roads:
        road=ET.SubElement(root,'road',id=str(ident),name=f'C382355_{ident}',
                           length=str(length),junction=str(junction))
        link=ET.SubElement(road,'link')
        if ident==1:ET.SubElement(link,'successor',elementType='junction',elementId='100')
        if ident in (2,4):ET.SubElement(link,'predecessor',elementType='junction',elementId='100')
        if ident==13:
            ET.SubElement(link,'predecessor',elementType='road',elementId='1',contactPoint='end')
            ET.SubElement(link,'successor',elementType='road',elementId='4',contactPoint='start')
        if ident==14:
            ET.SubElement(link,'predecessor',elementType='road',elementId='1',contactPoint='end')
            ET.SubElement(link,'successor',elementType='road',elementId='2',contactPoint='start')
        geometry=ET.SubElement(ET.SubElement(road,'planView'),'geometry',s='0',x=str(x),y=str(y),
                               hdg=str(heading),length=str(length))
        ET.SubElement(geometry,'arc',curvature=str(-1/7)) if ident==13 else ET.SubElement(geometry,'line')
        ET.SubElement(ET.SubElement(road,'elevationProfile'),'elevation',s='0',a='0',b='0',c='0',d='0')
        lanes=ET.SubElement(road,'lanes');ET.SubElement(lanes,'laneOffset',s='0',a='0',b='0',c='0',d='0')
        section=ET.SubElement(lanes,'laneSection',s='0')
        for side,ids in (('left',(1,2)),('center',(0,)),('right',(-1,-2))):
            group=ET.SubElement(section,side)
            for lane_id in ids:
                lane=ET.SubElement(group,'lane',id=str(lane_id),type='none' if lane_id==0 else 'driving',level='false')
                if lane_id:
                    if ident in (13,14):
                        lane_link=ET.SubElement(lane,'link')
                        ET.SubElement(lane_link,'predecessor',id=str(lane_id))
                        ET.SubElement(lane_link,'successor',id=str(lane_id))
                    ET.SubElement(lane,'width',sOffset='0',a=str(LANE_WIDTH_M),b='0',c='0',d='0')
                mark='solid' if lane_id==0 else 'broken'
                ET.SubElement(lane,'roadMark',sOffset='0',type=mark,
                              color='yellow' if lane_id==0 else 'white',width='0.12')
        objects=ET.SubElement(road,'objects')
        if ident==1:
            # Authored lane cue only; Native rendering and regulatory meaning
            # need saved-pixel and map review before the branch is certified.
            ET.SubElement(objects,'object',id='right_turn_arrow_1',name='right_turn_arrow',
                          type='roadMark',s='75',t='-5.25',zOffset='0',hdg='0',
                          pitch='0',roll='0',orientation='+',length='3',width='1.5',height='0')
        ET.SubElement(road,'signals')
    junction=ET.SubElement(root,'junction',id='100',name='right_turn_lane_connector')
    connection=ET.SubElement(junction,'connection',id='0',incomingRoad='1',connectingRoad='13',contactPoint='start')
    ET.SubElement(connection,'laneLink',**{'from':'-2','to':'-2'})
    straight=ET.SubElement(junction,'connection',id='1',incomingRoad='1',connectingRoad='14',contactPoint='start')
    ET.SubElement(straight,'laneLink',**{'from':'-2','to':'-2'})
    return ET.tostring(root,encoding='unicode')


def route(approach_y_m,turn_entry_x_m=-7):
    if approach_y_m not in CASE_APPROACH_Y_M.values():raise ValueError('Unknown approach lane')
    if turn_entry_x_m not in (-7,-10):raise ValueError('Unknown turn entry station')
    count=round((turn_entry_x_m+50)/.1)
    points=[[-50+i*.1,approach_y_m] for i in range(count+1)]
    p0=(turn_entry_x_m,approach_y_m);p1=(turn_entry_x_m+4,approach_y_m)
    p2=(-5.25,-3);p3=(-5.25,-7)
    for i in range(1,151):
        t=i/150
        points.append([(1-t)**3*p0[j]+3*(1-t)**2*t*p1[j]+3*(1-t)*t*t*p2[j]+t**3*p3[j]
                       for j in (0,1)])
    points.extend([[-5.25,-7-i*.1] for i in range(1,431)])
    return points


def straight_route(approach_y_m=-5.25,join_x_m=-7):
    if approach_y_m!=-5.25 or join_x_m not in (-7,-10):
        raise ValueError('Unknown right-only-lane straight probe')
    start=-55 if join_x_m==-10 else -50
    return [[start+i*.1,approach_y_m] for i in range(round((50-start)/.1)+1)]


def check():
    from shapely.geometry import Point,Polygon,box
    from shapely.ops import unary_union
    root=ET.fromstring(open_drive())
    roads={int(r.attrib['id']):r for r in root.findall('road')}
    assert set(roads)=={1,2,3,4,13,14}
    assert roads[13].find('planView/geometry/arc').attrib['curvature']==str(-1/7)
    assert roads[1].find('link/successor').attrib['elementId']=='100'
    assert roads[13].find('link/successor').attrib['elementId']=='4'
    assert roads[14].find('link/successor').attrib['elementId']=='2'
    arrow=roads[1].find('objects/object')
    assert arrow is not None and arrow.attrib['name']=='right_turn_arrow' and arrow.attrib['t']=='-5.25'
    links=root.findall('junction/connection/laneLink')
    assert len(links)==2 and all(link.attrib=={'from':'-2','to':'-2'} for link in links)
    surface=unary_union((box(-100,-7,100,7),box(-7,-100,7,100)))
    results={}
    for suffix,lateral in CASE_APPROACH_Y_M.items():
        for entry in (-7,-10):
            points=route(lateral,entry) if suffix=='controlled_1' else straight_route(lateral,entry)
            assert all(surface.covers(Point(p)) for p in points)
            gaps=[math.dist(a,b) for a,b in zip(points,points[1:])]
            assert max(gaps)<.3
            for a,b in zip(points,points[1:]):
                angle=math.atan2(b[1]-a[1],b[0]-a[0]);c=math.cos(angle);s=math.sin(angle)
                body=Polygon([(a[0]+c*u-s*v,a[1]+s*u+c*v) for u,v in
                              ((-2.6,-1.1),(-2.6,1.1),(2.6,1.1),(2.6,-1.1))])
                assert surface.covers(body),'Prospective body leaves authored pavement'
            results[f'{suffix}:entry{entry}']={'route_points':len(points),'maximum_gap_m':max(gaps),
                'requested_approach_y_m':lateral,'turn_entry_x_m':entry,
                'requested_movement':'right_turn' if suffix=='controlled_1' else 'straight_through'}
    return {'passed':True,'cases':results,'authored_right_turn_lane_id':-2,
            'right_turn_lane_design_and_signage_native_verified':False,
            'lane_link_native_verified':False,'straight_connector_present_for_diagnostic':True,
            'frozen_cell_maneuver_fit_of_straight_probe_unverified':True,
            'legal_outcome_claimed':False}


if __name__=='__main__':print(json.dumps(check()))
