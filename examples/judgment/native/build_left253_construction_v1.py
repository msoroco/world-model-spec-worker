"""Isolated left253 OpenDRIVE proposal and offline geometry check, not acceptance.

The legal-region assumption derives from the prolonged lateral roadway bounds of
four orthogonal 14m-wide roadway legs. Native junction bounds are never substituted.
"""
import argparse, hashlib, json, math, shutil
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parent


def xodr():
    root=ET.Element('OpenDRIVE')
    ET.SubElement(root,'header',revMajor='1',revMinor='4',name='C329654-left253-intersection-v1',version='1',date='2026-10-20',north='160',south='-160',east='160',west='-160',vendor='scenario_pipeline')
    specs=[(1,-160,0,0,153,None,None,('junction',100,None)),(2,7,0,0,153,None,('junction',100,None),None),(3,0,-160,math.pi/2,153,None,None,('junction',100,None)),(4,0,7,math.pi/2,153,None,('junction',100,None),None),(11,-7,0,0,14,None,('road',1,'end'),('road',2,'start')),(12,0,-7,math.pi/2,14,None,('road',3,'end'),('road',4,'start')),(13,-7,0,0,7*math.pi/2,1/7.,('road',1,'end'),('road',4,'start'))]
    for ident,x,y,hdg,length,curvature,pred,succ in specs:
        r=ET.SubElement(root,'road',name='left253_'+str(ident),id=str(ident),length=str(length),junction='100' if ident>=11 else '-1')
        link=ET.SubElement(r,'link')
        for name,item in [('predecessor',pred),('successor',succ)]:
            if item:
                a={'elementType':item[0],'elementId':str(item[1])}
                if item[2]:a['contactPoint']=item[2]
                ET.SubElement(link,name,**a)
        g=ET.SubElement(ET.SubElement(r,'planView'),'geometry',s='0',x=str(x),y=str(y),hdg=str(hdg),length=str(length))
        ET.SubElement(g,'arc',curvature=str(curvature)) if curvature else ET.SubElement(g,'line')
        ET.SubElement(ET.SubElement(r,'elevationProfile'),'elevation',s='0',a='0',b='0',c='0',d='0')
        ET.SubElement(r,'lateralProfile');lanes=ET.SubElement(r,'lanes')
        ET.SubElement(lanes,'laneOffset',s='0',a='0',b='0',c='0',d='0')
        sec=ET.SubElement(lanes,'laneSection',s='0')
        for side,ids in [('left',[1,2]),('center',[0]),('right',[-1,-2])]:
            group=ET.SubElement(sec,side)
            for lane_id in ids:
                lane=ET.SubElement(group,'lane',id=str(lane_id),type='driving' if lane_id else 'none',level='false')
                if lane_id:
                    links=ET.SubElement(lane,'link')
                    if ident>=11:
                        ET.SubElement(links,'predecessor',id=str(lane_id));ET.SubElement(links,'successor',id=str(lane_id))
                    ET.SubElement(lane,'width',sOffset='0',a='3.5',b='0',c='0',d='0')
                ET.SubElement(lane,'roadMark',sOffset='0',type='solid' if lane_id==0 or abs(lane_id)==2 else 'broken',weight='standard',color='yellow' if lane_id==0 else 'white',width='.12',laneChange='none' if lane_id==0 else 'both')
        ET.SubElement(r,'objects');ET.SubElement(r,'signals')
    junction=ET.SubElement(root,'junction',id='100',name='connected_two_way_to_two_way')
    for i,(incoming,connecting,contact,ids) in enumerate([(1,11,'start',[-1,-2]),(2,11,'end',[1,2]),(3,12,'start',[-1,-2]),(4,12,'end',[1,2]),(1,13,'start',[-1,-2]),(4,13,'end',[1,2])]):
        c=ET.SubElement(junction,'connection',id=str(i),incomingRoad=str(incoming),connectingRoad=str(connecting),contactPoint=contact)
        for lane_id in ids:ET.SubElement(c,'laneLink',**{'from':str(lane_id),'to':str(lane_id)})
    return ET.tostring(root,encoding='unicode')


def routes():
    ego=[(-52+i*.1,-1.75) for i in range(451)]
    radius=8.75
    ego.extend((-7+radius*math.sin(i*math.pi/800),7-radius*math.cos(i*math.pi/800)) for i in range(1,401))
    ego.extend((1.75,7+i*.1) for i in range(1,451))
    opposing=[(140-i*.1,1.75) for i in range(2801)]
    return {'ego':ego,'opposing':opposing}


def surface():
    from shapely.geometry import Polygon,box
    from shapely.ops import unary_union
    outer=[(-7+14*math.sin(i*math.pi/1024),7-14*math.cos(i*math.pi/1024)) for i in range(513)]
    inner=[(-7,7)]
    return unary_union([box(-160,-7,160,7),box(-7,-160,7,160),Polygon(outer+inner)])


def check():
    from shapely.geometry import Point,Polygon
    road=ET.fromstring(xodr());rs=routes();pavement=surface()
    assert len(road.findall('junction/connection'))==6
    assert not road.findall('.//signal')
    for ident in (1,2,3,4,11,12,13):
        r=next(r for r in road.findall('road') if r.attrib['id']==str(ident))
        assert len(r.findall('./lanes/laneSection/left/lane'))==2 and len(r.findall('./lanes/laneSection/right/lane'))==2
    assert rs['ego'][0]==(-52.,-1.75) and rs['ego'][-1]==(1.75,52.)
    for name,points in rs.items():
        assert all(pavement.covers(Point(x,y)) for x,y in points)
        assert max(math.hypot(b[0]-a[0],b[1]-a[1]) for a,b in zip(points,points[1:]))<.101
    # Prospective envelope check uses a documented asset-sized construction proxy,
    # never a replacement for the actual queried native full body before driving.
    max_error=0.;bounds=[]
    for points in rs.values():
        for a,b in zip(points,points[1:]):
            angle=math.atan2(b[1]-a[1],b[0]-a[0]);c,s=math.cos(angle),math.sin(angle)
            corners=[(a[0]+c*x-s*y,a[1]+s*x+c*y) for x,y in [(-2.6,-1.1),(-2.6,1.1),(2.6,1.1),(2.6,-1.1)]]
            assert pavement.covers(Polygon(corners)), 'Prospective body proxy leaves authored pavement'
    return {'passed':True,'native_verified':False,'delivery_supported':False,'route_samples':{k:len(v) for k,v in rs.items()},'roadway_width_m':14,'intersection_region_authored_xy_m':[[-7,-7],[7,-7],[7,7],[-7,7]],'region_provenance':'Prolonged x/y lateral roadway boundaries at +/-7m of four orthogonal two-way legs; NRS-484A-105 external geometric assumption; reconcile with native surveyed boundaries','native_junction_bbox_is_legal_region':False,'prospective_body_proxy_m':[5.2,2.2],'native_asset_envelopes_and_surfaces':'pending live survey before motion','signal_approach_to_course_change_m':45,'construction_margin_m':36.576,'no_hazard_threshold':True}


def build(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    (destination/'scene-left253-v1.xodr').write_text(xodr())
    (destination/'routes-left253-v1.json').write_text(json.dumps(routes()))
    (destination/'offline-geometry-check.json').write_text(json.dumps(check(),indent=2)+'\n')
    return destination

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--check',action='store_true');a.add_argument('--output');args=a.parse_args()
    if args.check:print(json.dumps(check()))
    else:assert args.output;print(build(args.output))
