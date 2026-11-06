"""CPU-authored C394300 left-turn-onto-highway and merge route proposals.

This geometry does not certify CARLA lane designation, vehicle tracking, or
actual post-turn distance. Saved Native samples determine those observables.
"""
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

STEP_M = .1
LANE_WIDTH_M = 3.5
TURN_END_X = -66.5
TARGET_FEET = {'below_50_ft':45, 'at_50_ft':50, 'above_50_ft':55}


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C394300-after-left-turn-draft',
                  version='1', date='2026-11-05', north='100', south='-100',
                  east='100', west='-100', vendor='full-train-worker')
    # CARLA reflects OpenDRIVE y on import. Author northbound/right-curving
    # coordinates so the observed Native movement is southbound then left/east.
    roads = [(4,-73.5,-50,math.pi/2,44.75,-1),
             (13,-73.5,-5.25,math.pi/2,7*math.pi/2,100),
             (1,-66.5,1.75,0,166.5,-1)]
    for ident,x,y,heading,length,junction in roads:
        road = ET.SubElement(root,'road',id=str(ident),name=f'C394300_3c_{ident}',
                             length=str(length),junction=str(junction))
        link = ET.SubElement(road,'link')
        if ident == 4: ET.SubElement(link,'successor',elementType='junction',elementId='100')
        if ident == 13:
            ET.SubElement(link,'predecessor',elementType='road',elementId='4',contactPoint='end')
            ET.SubElement(link,'successor',elementType='road',elementId='1',contactPoint='start')
        if ident == 1: ET.SubElement(link,'predecessor',elementType='junction',elementId='100')
        geom = ET.SubElement(ET.SubElement(road,'planView'),'geometry',s='0',x=str(x),y=str(y),
                             hdg=str(heading),length=str(length))
        if ident == 13: ET.SubElement(geom,'arc',curvature=str(-1/7))
        else: ET.SubElement(geom,'line')
        ET.SubElement(ET.SubElement(road,'elevationProfile'),'elevation',s='0',a='0',b='0',c='0',d='0')
        lanes = ET.SubElement(road,'lanes')
        ET.SubElement(lanes,'laneOffset',s='0',a='0',b='0',c='0',d='0')
        section = ET.SubElement(lanes,'laneSection',s='0')
        for side, ids in (('left',(1,)),('center',(0,)),
                          ('right',(-1,) if ident==13 else (-1,-2))):
            group = ET.SubElement(section,side)
            for lane_id in ids:
                lane = ET.SubElement(group,'lane',id=str(lane_id),
                                     type='none' if lane_id==0 else 'driving',level='false')
                if lane_id:
                    ET.SubElement(lane,'width',sOffset='0',a=str(LANE_WIDTH_M),b='0',c='0',d='0')
                if ident==13 and lane_id==-1:
                    ll=ET.SubElement(lane,'link')
                    ET.SubElement(ll,'predecessor',id='-1');ET.SubElement(ll,'successor',id='-1')
                ET.SubElement(lane,'roadMark',sOffset='0',type='broken' if lane_id else 'solid',
                              color='yellow' if lane_id in (0,-1) else 'white',width='0.12')
        ET.SubElement(road,'objects');ET.SubElement(road,'signals')
    junction=ET.SubElement(root,'junction',id='100',name='left_onto_center_lane')
    connection=ET.SubElement(junction,'connection',id='0',incomingRoad='4',
                             connectingRoad='13',contactPoint='start')
    ET.SubElement(connection,'laneLink',**{'from':'-1','to':'-1'})
    return ET.tostring(root,encoding='unicode')


def route(case, merge_length_m=8.0, start_y_m=45.0):
    if case not in TARGET_FEET: raise ValueError('Unknown draft case')
    if not 6 <= merge_length_m <= 12: raise ValueError('Unsupported merge length')
    if start_y_m not in (42.0,45.0): raise ValueError('Unsupported inbound start')
    points=[]
    for i in range(round((start_y_m-5.1)/STEP_M)+1):
        points.append([-71.75,round(-start_y_m+i*STEP_M,5)])
    # The authored -1 lane center turns clockwise at radius 5.25 m;
    # reflection on import makes this a Native left turn.
    for i in range(1,151):
        theta=math.pi-i*(math.pi/2)/150
        points.append([round(TURN_END_X+5.25*math.cos(theta),5),
                       round(-5.25+5.25*math.sin(theta),5)])
    nominal=TARGET_FEET[case]*.3048
    # First body contact with the through lane precedes full center arrival.
    # This station is a command only; the saved Native event interval decides.
    merge_start=TURN_END_X+nominal+.19*merge_length_m
    for i in range(1,1501):
        x=TURN_END_X+i*STEP_M
        phase=max(0,min(1,(x-merge_start)/merge_length_m))
        smooth=phase*phase*(3-2*phase)
        points.append([round(x,5),round(-3.5*smooth,5)])
    return points


def check():
    root=ET.fromstring(open_drive())
    roads={int(row.attrib['id']):row for row in root.findall('road')}
    assert set(roads)=={1,4,13}
    assert roads[4].find('link/successor').attrib['elementId']=='100'
    assert roads[13].find('link/predecessor').attrib['elementId']=='4'
    assert roads[13].find('link/successor').attrib['elementId']=='1'
    assert roads[1].find('link/predecessor').attrib['elementId']=='100'
    assert [(x.attrib['from'],x.attrib['to']) for x in root.findall('junction/connection/laneLink')]==[('-1','-1')]
    # Exact rectangle-union coverage without a nonportable geometry dependency.
    pavement=((-76,-5.25,100,5.25),(-76,-50,-66.5,0))
    def covered(point):
        x,y=point
        return any(a-1e-8<=x<=c+1e-8 and b-1e-8<=y<=d+1e-8
                   for a,b,c,d in pavement)
    def segment_covered(a,b):
        cuts={0.0,1.0}
        for axis in (0,1):
            delta=b[axis]-a[axis]
            if abs(delta)>1e-12:
                for rectangle in pavement:
                    for boundary in (rectangle[axis],rectangle[axis+2]):
                        t=(boundary-a[axis])/delta
                        if 0<t<1:cuts.add(t)
        times=sorted(cuts)
        return all(covered((a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t))
                   for left,right in zip(times,times[1:])
                   for t in (left,(left+right)/2,right))
    results={}
    for case, feet in TARGET_FEET.items():
        points=route(case)
        gaps=[math.dist(a,b) for a,b in zip(points,points[1:])]
        assert max(gaps)<.15, 'Route discontinuity'
        for a,b in zip(points,points[1:]):
            assert covered(a), 'Route leaves pavement'
            angle=math.atan2(b[1]-a[1],b[0]-a[0]);c=math.cos(angle);s=math.sin(angle)
            body=[(a[0]+c*u-s*v,a[1]+s*u+c*v) for u,v in
                  ((-2.5,-1),(-2.5,1),(2.5,1),(2.5,-1))]
            assert all(segment_covered(p,body[(i+1)%4]) for i,p in enumerate(body)), \
                'Prospective body leaves pavement'
        results[case]={'nominal_commanded_after_turn_ft':feet,'route_points':len(points),
                       'maximum_sample_gap_m':round(max(gaps),5),
                       'nominal_merge_start_x_m':round(TURN_END_X+feet*.3048+.19*8,5)}
    assert len({v['nominal_merge_start_x_m'] for v in results.values()})==3
    return {'passed':True,'scope':'authored OpenDRIVE, route and body proxy only',
            'native_center_lane_design_verified':False,'native_connector_identity_verified':False,
            'cases':results}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output');args=parser.parse_args()
    result=check()
    if args.output:
        output=Path(args.output);output.mkdir(parents=True,exist_ok=False)
        (output/'scene.xodr').write_text(open_drive())
        for case in TARGET_FEET:
            (output/f'route-{case}.json').write_text(json.dumps(route(case)))
        (output/'geometry-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
