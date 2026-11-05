"""Authored same-cell center-turn-lane map and five left-turn route proposals.

The XML and routes are CPU constructions. Native lane designation, connector
identity, vehicle tracking, and physical 200-foot event distances are unproven.
"""
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

STEP_M=.1
LANE_WIDTH_M=3.5
TURN_START_X=-10.0
TARGET_FEET={'witness_1':180,'witness_2':220,
             'numeric_1_0':199,'numeric_1_1':200,'numeric_1_2':201}


def open_drive():
    root=ET.Element('OpenDRIVE')
    ET.SubElement(root,'header',revMajor='1',revMinor='4',name='C394300-center-turn-lane-draft',
                  version='1',date='2026-11-05',north='100',south='-100',east='100',west='-100',vendor='full-train-worker')
    roads=[(1,-100,1.75,0,90,-1),(2,-10,1.75,0,100,-1),
           (4,-4.75,7,math.pi/2,80,-1),(13,-10,1.75,0,5.25*math.pi/2,100)]
    for ident,x,y,heading,length,junction in roads:
        road=ET.SubElement(root,'road',id=str(ident),name=f'C394300_{ident}',
                           length=str(length),junction=str(junction))
        link=ET.SubElement(road,'link')
        if ident==1:ET.SubElement(link,'successor',elementType='junction',elementId='100')
        if ident==4:ET.SubElement(link,'predecessor',elementType='junction',elementId='100')
        if ident==13:
            ET.SubElement(link,'predecessor',elementType='road',elementId='1',contactPoint='end')
            ET.SubElement(link,'successor',elementType='road',elementId='4',contactPoint='start')
        geometry=ET.SubElement(ET.SubElement(road,'planView'),'geometry',s='0',
            x=str(x),y=str(y),hdg=str(heading),length=str(length))
        ET.SubElement(geometry,'arc',curvature=str(1/5.25)) if ident==13 else ET.SubElement(geometry,'line')
        ET.SubElement(ET.SubElement(road,'elevationProfile'),'elevation',s='0',a='0',b='0',c='0',d='0')
        lanes=ET.SubElement(road,'lanes')
        ET.SubElement(lanes,'laneOffset',s='0',a='0',b='0',c='0',d='0')
        section=ET.SubElement(lanes,'laneSection',s='0')
        for side,ids in (('left',(1,)),('center',(0,)),('right',(-1,-2))):
            group=ET.SubElement(section,side)
            for lane_id in ids:
                lane=ET.SubElement(group,'lane',id=str(lane_id),
                    type='none' if lane_id==0 else 'driving',level='false')
                if lane_id:
                    ET.SubElement(lane,'width',sOffset='0',a=str(LANE_WIDTH_M),b='0',c='0',d='0')
                    if ident==13 and lane_id==-1:
                        ll=ET.SubElement(lane,'link')
                        ET.SubElement(ll,'predecessor',id='-1');ET.SubElement(ll,'successor',id='-1')
                ET.SubElement(lane,'roadMark',sOffset='0',type='broken' if lane_id else 'solid',
                    color='yellow' if lane_id in (0,-1) else 'white',width='0.12')
        ET.SubElement(road,'objects');ET.SubElement(road,'signals')
    junction=ET.SubElement(root,'junction',id='100',name='center_lane_left_turn')
    connection=ET.SubElement(junction,'connection',id='0',incomingRoad='1',
                             connectingRoad='13',contactPoint='start')
    ET.SubElement(connection,'laneLink',**{'from':'-1','to':'-1'})
    return ET.tostring(root,encoding='unicode')


def route(case,start_x_m=-95):
    if case not in TARGET_FEET:raise ValueError('Unknown planned case')
    if start_x_m not in (-95,-98):raise ValueError('Unknown candidate route start')
    nominal_m=TARGET_FEET[case]*.3048
    # The command stations are nominal; the source-body contact and turn
    # brackets, not this path request, determine any measured distance.
    entry_x=TURN_START_X-nominal_m
    lane_change_start=entry_x-10
    points=[]
    count=round((TURN_START_X-start_x_m)/STEP_M)
    for i in range(count+1):
        x=start_x_m+i*STEP_M
        phase=max(0,min(1,(x-lane_change_start)/10))
        smooth=phase*phase*(3-2*phase)
        points.append([round(x,5),round(-3.5+3.5*smooth,5)])
    p0=(-10,0);p1=(-6.5,0);p2=(-3,3.5);p3=(-3,7)
    for i in range(1,151):
        t=i/150
        x=(1-t)**3*p0[0]+3*(1-t)**2*t*p1[0]+3*(1-t)*t*t*p2[0]+t**3*p3[0]
        y=(1-t)**3*p0[1]+3*(1-t)**2*t*p1[1]+3*(1-t)*t*t*p2[1]+t**3*p3[1]
        points.append([round(x,5),round(y,5)])
    points.extend([[-3,round(7+i*STEP_M,5)] for i in range(1,601)])
    return points


def check():
    root=ET.fromstring(open_drive())
    roads={int(row.attrib['id']):row for row in root.findall('road')}
    assert set(roads)=={1,2,4,13}
    assert roads[1].find('link/successor').attrib['elementId']=='100'
    assert roads[13].find('link/predecessor').attrib['elementId']=='1'
    assert roads[13].find('link/successor').attrib['elementId']=='4'
    assert roads[4].find('link/predecessor').attrib['elementId']=='100'
    assert [(v.attrib['from'],v.attrib['to']) for v in root.findall('junction/connection/laneLink')]==[('-1','-1')]
    from shapely.geometry import LineString,Point,Polygon,box
    from shapely.ops import unary_union
    surface=unary_union((box(-100,-5.25,90,5.25),box(-10,-5,5,9),box(-6.5,7,.5,90)))
    results={}
    for case,feet in TARGET_FEET.items():
        points=route(case)
        gaps=[math.dist(a,b) for a,b in zip(points,points[1:])]
        assert max(gaps)<.25,'Route has a discontinuity'
        assert all(surface.covers(Point(*point)) for point in points),'Route leaves pavement'
        for a,b in zip(points,points[1:]):
            angle=math.atan2(b[1]-a[1],b[0]-a[0]);c=math.cos(angle);s=math.sin(angle)
            body=Polygon([(a[0]+c*u-s*v,a[1]+s*u+c*v) for u,v in
                          ((-2.5,-1),(-2.5,1),(2.5,1),(2.5,-1))])
            assert surface.covers(body),'Prospective body leaves authored pavement'
        results[case]={'nominal_commanded_center_lane_distance_ft':feet,
                       'nominal_commanded_entry_station_x_m':round(TURN_START_X-feet*.3048,5),
                       'lateral_at_x_minus_80_m':points[150][1],
                       'route_points':len(points),
                       'route_length_m':round(LineString(points).length,3),
                       'maximum_sample_gap_m':round(max(gaps),5)}
    assert len({route(case)[150][1] for case in TARGET_FEET})>1, 'Controlled entry routes are identical'
    return {'passed':True,'scope':'authored OpenDRIVE, route and prospective body proxy only',
            'native_center_lane_design_verified':False,
            'native_connector_identity_verified':False,
            'cases':results}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output');args=parser.parse_args()
    result=check()
    if args.output:
        output=Path(args.output);output.mkdir(parents=True,exist_ok=False)
        (output/'scene.xodr').write_text(open_drive())
        for case in TARGET_FEET:(output/f'route-{case}.json').write_text(json.dumps(route(case)))
        (output/'geometry-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
