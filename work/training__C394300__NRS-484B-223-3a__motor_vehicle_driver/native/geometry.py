"""Authored two-turn-opportunity map for the 3(a) purpose comparison.

This is a CPU proposal. The first case turns left from the center lane at the
first opportunity. The second continues through that opportunity, leaves the
center lane for the through lane, then turns left at a later opportunity. The
route itself does not establish driver purpose or Native feasibility.
"""
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

STEP_M=.1
CASES=('controlled_1','controlled_2')


def _road(root, ident, x, y, heading, length, junction=-1, center_turn=False, arc=False):
    road=ET.SubElement(root,'road',id=str(ident),name=f'C394300_3a_{ident}',
                       length=str(length),junction=str(junction))
    ET.SubElement(road,'link')
    geom=ET.SubElement(ET.SubElement(road,'planView'),'geometry',s='0',
                       x=str(x),y=str(y),hdg=str(heading),length=str(length))
    ET.SubElement(geom,'arc',curvature=str(1/5.25)) if arc else ET.SubElement(geom,'line')
    ET.SubElement(ET.SubElement(road,'elevationProfile'),'elevation',
                  s='0',a='0',b='0',c='0',d='0')
    lanes=ET.SubElement(road,'lanes')
    ET.SubElement(lanes,'laneOffset',s='0',a='0',b='0',c='0',d='0')
    section=ET.SubElement(lanes,'laneSection',s='0')
    for side,ids in (('left',(1,)),('center',(0,)),('right',(-1,-2))):
        group=ET.SubElement(section,side)
        for lid in ids:
            turn=center_turn and lid==-1
            lane=ET.SubElement(group,'lane',id=str(lid),
                               type='none' if lid==0 else 'bidirectional' if turn else 'driving',
                               level='false')
            if lid:
                ET.SubElement(lane,'width',sOffset='0',a='3.5',b='0',c='0',d='0')
                if ident in (13,14,23) and lid==-1:
                    lane_link=ET.SubElement(lane,'link')
                    ET.SubElement(lane_link,'predecessor',id='-1' if ident!=23 else '-2')
                    ET.SubElement(lane_link,'successor',id='-1')
                if turn:
                    ET.SubElement(lane,'userData',code='lane_use',value='left_turn_only_both_directions')
            ET.SubElement(lane,'roadMark',sOffset='0',type='broken' if lid else 'solid',
                          color='yellow' if lid in (0,-1) else 'white',width='0.12')
    ET.SubElement(road,'objects');ET.SubElement(road,'signals')
    return road


def open_drive():
    root=ET.Element('OpenDRIVE')
    ET.SubElement(root,'header',revMajor='1',revMinor='4',name='C394300-3a-purpose-draft',
                  version='1',date='2026-11-06',north='100',south='-100',
                  east='100',west='-100',vendor='full-train-worker')
    # CARLA reflects authored y on import. Positive authored y after the
    # eastbound turn therefore becomes a Native left turn toward south.
    inbound=_road(root,1,-100,1.75,0,90,center_turn=True)
    straight=_road(root,14,-10,1.75,0,1,junction=100,center_turn=True)
    second=_road(root,2,-9,1.75,0,49,center_turn=True)
    first_turn=_road(root,13,-10,1.75,0,5.25*math.pi/2,junction=100,arc=True)
    first_exit=_road(root,4,-4.75,7,math.pi/2,70)
    second_turn=_road(root,23,40,-1.75,0,5.25*math.pi/2,junction=200,arc=True)
    second_exit=_road(root,24,45.25,3.5,math.pi/2,70)
    for road,junction in ((inbound,100),(second,200)):
        ET.SubElement(road.find('link'),'successor',elementType='junction',elementId=str(junction))
    for road,prior in ((straight,1),(first_turn,1),(second_turn,2)):
        ET.SubElement(road.find('link'),'predecessor',elementType='road',elementId=str(prior),contactPoint='end')
    for road,prior in ((second,100),(first_exit,100),(second_exit,200)):
        ET.SubElement(road.find('link'),'predecessor',elementType='junction',elementId=str(prior))
    for road,target in ((straight,2),(first_turn,4),(second_turn,24)):
        ET.SubElement(road.find('link'),'successor',elementType='road',elementId=str(target),contactPoint='start')
    for ident,incoming,connecting,lane_from,lane_to in (
        (100,1,13,-1,-1),(100,1,14,-1,-1),(200,2,23,-2,-1)):
        junction=root.find(f"./junction[@id='{ident}']")
        if junction is None:junction=ET.SubElement(root,'junction',id=str(ident),name=f'purpose_choice_{ident}')
        connection=ET.SubElement(junction,'connection',id=str(len(junction.findall('connection'))),
                                 incomingRoad=str(incoming),connectingRoad=str(connecting),contactPoint='start')
        ET.SubElement(connection,'laneLink',**{'from':str(lane_from),'to':str(lane_to)})
    return ET.tostring(root,encoding='unicode')


def _smooth(t):
    t=max(0,min(1,t));return t*t*(3-2*t)


def route(case):
    if case not in CASES:raise ValueError('Unknown purpose comparison case')
    points=[]
    for index in range(851):
        x=-95+index*STEP_M
        y=-3.5+3.5*_smooth((x+75)/10)
        points.append([round(x,5),round(y,5)])
    if case=='controlled_1':
        # Turn at the first center-lane opportunity after common entry.
        p0=(-10,0);p1=(-6.5,0);p2=(-3,3.5);p3=(-3,7)
        for index in range(1,151):
            t=index/150
            x=(1-t)**3*p0[0]+3*(1-t)**2*t*p1[0]+3*(1-t)*t*t*p2[0]+t**3*p3[0]
            y=(1-t)**3*p0[1]+3*(1-t)**2*t*p1[1]+3*(1-t)*t*t*p2[1]+t**3*p3[1]
            points.append([round(x,5),round(y,5)])
        points.extend([[-3,round(7+index*STEP_M,5)] for index in range(1,401)])
    else:
        # Cross the first turn opportunity in the center lane, then leave it
        # for the adjacent through lane before a later left turn.
        for index in range(1,501):
            x=-10+index*STEP_M
            y=-3.5*_smooth((x-20)/10)
            points.append([round(x,5),round(y,5)])
        p0=(40,-3.5);p1=(43.5,-3.5);p2=(47,0);p3=(47,3.5)
        for index in range(1,151):
            t=index/150
            x=(1-t)**3*p0[0]+3*(1-t)**2*t*p1[0]+3*(1-t)*t*t*p2[0]+t**3*p3[0]
            y=(1-t)**3*p0[1]+3*(1-t)**2*t*p1[1]+3*(1-t)*t*t*p2[1]+t**3*p3[1]
            points.append([round(x,5),round(y,5)])
        points.extend([[47,round(3.5+index*STEP_M,5)] for index in range(1,401)])
    return points


def check():
    root=ET.fromstring(open_drive())
    assert {int(road.attrib['id']) for road in root.findall('road')}=={1,2,4,13,14,23,24}
    center=[(road.attrib['id'],lane) for road in root.findall('road')
            for lane in road.findall("./lanes/laneSection/right/lane[@type='bidirectional']")]
    assert [(road,lane.attrib['id']) for road,lane in center]==[('1','-1'),('14','-1'),('2','-1')]
    assert all(lane.find("userData[@code='lane_use']").attrib['value']=='left_turn_only_both_directions'
               for _,lane in center)
    links={(int(c.attrib['incomingRoad']),int(c.attrib['connectingRoad']),
            int(c.find('laneLink').attrib['from']))
           for c in root.findall('./junction/connection')}
    assert links=={(1,13,-1),(1,14,-1),(2,23,-2)}
    first,second=route('controlled_1'),route('controlled_2')
    assert first[:851]==second[:851]
    assert all(abs(y)<1e-8 for x,y in second if -10<=x<=20)
    assert any(x>=30 and abs(y+3.5)<1e-8 for x,y in second)
    assert first[-1][1]>40 and second[-1][1]>40
    gaps={case:max(math.dist(a,b) for a,b in zip(route(case),route(case)[1:])) for case in CASES}
    assert max(gaps.values())<.16
    return {'passed':True,'cases':{case:{'points':len(route(case)),
            'maximum_sample_gap_m':round(gaps[case],5)} for case in CASES},
            'authored_bidirectional_turn_only_center_lane':True,
            'native_lane_design_verified':False,'driver_purpose_verified':False,
            'physical_tracking_verified':False,
            'scope':'authored CPU route/link prototype; no Native readback, purpose inference or legal verdict'}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output');args=parser.parse_args()
    result=check()
    if args.output:
        output=Path(args.output);output.mkdir(parents=True,exist_ok=False)
        (output/'scene.xodr').write_text(open_drive())
        for case in CASES:(output/f'route-{case}.json').write_text(json.dumps(route(case)))
        (output/'geometry-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
