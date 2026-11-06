"""Authored C110454 railroad and one-way statutory alternatives, CPU only."""
from __future__ import annotations
import math
from xml.etree import ElementTree as ET
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
import geometry_base

CASES={
 'rail_reference':{'zone':'railroad_crossing','boundary_x_m':-20.0,'window':(-85.0,-65.0),'one_way':False},
 'rail_contrast':{'zone':'railroad_crossing','boundary_x_m':-20.0,'window':(-55.0,-35.0),'one_way':False},
 'oneway_absent':{'zone':'intersection','boundary_x_m':-7.0,'window':(-28.0,-8.0),'one_way':False},
 'oneway_present':{'zone':'intersection','boundary_x_m':-7.0,'window':(-28.0,-8.0),'one_way':True},
}
EXCURSION_WINDOWS={case:tuple(spec['window']) for case,spec in CASES.items()}
STATUTORY_APPROACH_M=30.48

def open_drive(case='rail_reference'):
    if case not in CASES:raise ValueError('Unknown statutory alternative')
    root=ET.fromstring(geometry_base.open_drive())
    if case.startswith('rail_'):
        road=next(r for r in root.findall('road') if r.attrib['id']=='1')
        ET.SubElement(road.find('objects'),'object',id='701',
            name='C110454-authored-railroad-grade-crossing',type='railroadCrossing',
            s='80',t='0',zOffset='0',hdg='0',length='2',width='7',height='0')
    if CASES[case]['one_way']:
        for road in root.findall('road'):
            if road.attrib['id'] not in ('1','2','13'):continue
            road.find('planView/geometry').attrib['y']='3.5'
            section=road.find('lanes/laneSection')
            left=section.find('left');left.clear()
            right=section.find('right')
            ET.SubElement(right,'lane',id='-2',type='driving',level='false')
            lane=right.findall('lane')[-1]
            if road.attrib['id']=='13':
                link=ET.SubElement(lane,'link')
                ET.SubElement(link,'predecessor',id='-2')
                ET.SubElement(link,'successor',id='-2')
            ET.SubElement(lane,'width',sOffset='0',a='3.5',b='0',c='0',d='0')
            ET.SubElement(lane,'roadMark',sOffset='0',type='broken',color='white',width='0.12')
            if road.attrib['id']=='2':
                road.find('objects/object').attrib['t']='-8.75'
        connection=next(c for c in root.findall('junction/connection') if c.attrib['incomingRoad']=='1')
        for link in connection.findall('laneLink'):
            if link.attrib['from']=='1':
                link.attrib.update({'from':'-2','to':'-2'})
    return ET.tostring(root,encoding='unicode')

def _smoothstep(t):return t*t*(3-2*t)

def route(case):
    if case not in CASES:raise ValueError('Unknown statutory alternative')
    start=-90 if case.startswith('rail_') else -70
    onset,end=CASES[case]['window']
    points=[]
    for index in range(round((12-start)/.1)+1):
        x=round(start+index*.1,4)
        if x<onset or x>end:y=-1.75
        elif x<=onset+5:y=-1.75+3.5*_smoothstep((x-onset)/5)
        elif x<=end-5:y=1.75
        else:y=1.75-3.5*_smoothstep((x-end+5)/5)
        points.append([x,round(y,6)])
    for index in range(1,81):
        t=index/80
        points.append([round(12+8*t,4),round(-1.75-3.5*_smoothstep(t),6)])
    return points

def check():
    pavement=unary_union((box(-100,-3.5,100,3.5),box(-3.5,-100,3.5,100),box(8,-7,35,-3.5)))
    outcomes={}
    for case,spec in CASES.items():
        root=ET.fromstring(open_drive(case))
        roads={r.attrib['id']:r for r in root.findall('road')}
        if set(roads)!={'1','2','3','4','13','14'}:raise ValueError('Same-cell roads missing')
        rail=root.findall(".//object[@id='701']")
        if len(rail)!=(1 if case.startswith('rail_') else 0):raise ValueError('Railroad crossing asset differs')
        right=roads['1'].find('lanes/laneSection/right')
        lanes={l.attrib['id'] for l in right.findall('lane')}
        left={l.attrib['id'] for l in roads['1'].find('lanes/laneSection/left').findall('lane')}
        if spec['one_way'] and (lanes!={'-1','-2'} or left):raise ValueError('Two co-directional Native lanes missing')
        if not spec['one_way'] and (lanes!={'-1'} or left!={'1'}):raise ValueError('Two-way Native lanes missing')
        points=route(case)
        if max(math.dist(a,b) for a,b in zip(points,points[1:]))>.15:raise ValueError('Route discontinuity')
        for x,y in points:
            body=Polygon([(x-2.6,y-1.1),(x-2.6,y+1.1),(x+2.6,y+1.1),(x+2.6,y-1.1)])
            if not pavement.covers(body):raise ValueError('Prospective body leaves authored pavement')
        left_body=[x for x,y in points if y-1.1>0 and x+2.6<spec['boundary_x_m']]
        if not left_body:raise ValueError('No left-side approach interval')
        nearest=spec['boundary_x_m']-(max(left_body)+2.6)
        relation='within_100_ft' if nearest<STATUTORY_APPROACH_M else 'outside_100_ft'
        expected='outside_100_ft' if case=='rail_reference' else 'within_100_ft'
        if relation!=expected:raise ValueError('Authored statutory distance contrast differs')
        outcomes[case]={'zone':spec['zone'],'one_way_proposed':spec['one_way'],
            'nearest_full_body_front_distance_m':round(nearest,4),'sampled_relation':relation,
            'route_points':len(points),'parking_end_xy_m':points[-1]}
    if outcomes['rail_reference']['parking_end_xy_m']!=outcomes['rail_contrast']['parking_end_xy_m']:
        raise ValueError('Railroad comparison endpoint differs')
    if outcomes['oneway_absent']['parking_end_xy_m']!=outcomes['oneway_present']['parking_end_xy_m']:
        raise ValueError('One-way comparison endpoint differs')
    return {'passed':True,'cell_id':'C110454','law_id':'NRS-484B-213-2b',
        'scope':'authored geometry and sampled prospective body, no Native physical or legal conclusion',
        'case_results':outcomes}
