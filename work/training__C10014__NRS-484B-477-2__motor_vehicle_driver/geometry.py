"""Authored alley and abutting entrance proposal; physical Native proof is pending."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ALLEY_ROAD_ID=1
ALLEY_LANE_ID=-1
LANE_WIDTH_M=4.0
ENTRANCE_BOUNDS_M=(-3.0,-4.0,3.0,0.0)
ACCESS_BOUNDS_M=(-3.0,-20.0,3.0,-4.0)
STOP_X_M={'reference':-12.0,'contrast':0.0}
STOP_Y_M=-2.0


def open_drive():
    root=ET.Element('OpenDRIVE')
    ET.SubElement(root,'header',revMajor='1',revMinor='4',
        name='C10014-alley-entrance-draft',version='1',date='2026-11-05',
        north='30',south='-30',east='70',west='-70',vendor='full-train-worker')
    for ident,x,y,heading,length,lanes in ((1,-60,0,0,120,(-1,1)),
                                             (2,0,-4,-1.5707963267948966,16,(-1,))):
        road=ET.SubElement(root,'road',id=str(ident),name=f'C10014_{ident}',
                           length=str(length),junction='-1')
        ET.SubElement(road,'link')
        geometry=ET.SubElement(ET.SubElement(road,'planView'),'geometry',
            s='0',x=str(x),y=str(y),hdg=str(heading),length=str(length))
        ET.SubElement(geometry,'line')
        ET.SubElement(ET.SubElement(road,'elevationProfile'),'elevation',
                      s='0',a='0',b='0',c='0',d='0')
        group=ET.SubElement(road,'lanes')
        ET.SubElement(group,'laneOffset',s='0',a='0',b='0',c='0',d='0')
        section=ET.SubElement(group,'laneSection',s='0')
        for side,ids in (('left',(1,) if 1 in lanes else ()),('center',(0,)),
                         ('right',(-1,))):
            side_group=ET.SubElement(section,side)
            for lane_id in ids:
                lane=ET.SubElement(side_group,'lane',id=str(lane_id),
                    type='none' if lane_id==0 else 'driving',level='false')
                if lane_id:
                    ET.SubElement(lane,'width',sOffset='0',a=str(3.0 if ident==2 else LANE_WIDTH_M),
                                  b='0',c='0',d='0')
                ET.SubElement(lane,'roadMark',sOffset='0',
                    type='solid' if lane_id==0 else 'broken',
                    color='yellow' if lane_id==0 else 'white',width='0.12')
        ET.SubElement(road,'objects');ET.SubElement(road,'signals')
    return ET.tostring(root,encoding='unicode')


def route(suffix,start_x_m=-45):
    if suffix not in STOP_X_M:raise ValueError('Unknown controlled alley case')
    if start_x_m not in (-45,-55):raise ValueError('Unknown proposed approach start')
    end=STOP_X_M[suffix]
    points=[]
    for step in range(round((end-start_x_m)/.1)+1):
        x=start_x_m+step*.1
        points.append((round(x,5),STOP_Y_M))
    return points


def check():
    root=ET.fromstring(open_drive())
    roads={int(r.attrib['id']):r for r in root.findall('road')}
    assert set(roads)=={1,2}
    assert roads[1].find('planView/geometry/line') is not None
    assert roads[2].find('planView/geometry/line') is not None
    assert ENTRANCE_BOUNDS_M[0]<ENTRANCE_BOUNDS_M[2]
    assert ENTRANCE_BOUNDS_M[1]<ENTRANCE_BOUNDS_M[3]
    assert ACCESS_BOUNDS_M[3]==ENTRANCE_BOUNDS_M[1]
    assert STOP_X_M['reference']+2.6<ENTRANCE_BOUNDS_M[0]
    assert STOP_X_M['contrast']-2.6>ENTRANCE_BOUNDS_M[0]
    assert STOP_X_M['contrast']+2.6<ENTRANCE_BOUNDS_M[2]
    for suffix in STOP_X_M:
        for start in (-45,-55):
            points=route(suffix,start)
            assert points[0]==(start,STOP_Y_M)
            assert abs(points[-1][0]-STOP_X_M[suffix])<1e-8
            assert all(-4<-2-1.1 and -2+1.1<0 for _ in points)
            assert max(abs(b[0]-a[0]) for a,b in zip(points,points[1:]))<=.100001
    return {'roads':sorted(roads),'route_points':{s:len(route(s)) for s in STOP_X_M},
            'scope':'authored geometry only; no Native lane or access proof'}


if __name__=='__main__':
    print(json.dumps(check(),indent=2))
