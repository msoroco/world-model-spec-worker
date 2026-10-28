"""Right turn at a two-directional business-frontage intersection."""
import math
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def build_xodr():
    root=ET.parse(ROOT/'intersection.xodr').getroot()
    root.find('header').set('name','C378304-business-right-turn')
    # Physical objects are authored in addition to synthetic district status.
    # Whether CARLA renders them or makes their use legible remains a live
    # capability measurement, not a CPU assertion.
    west=root.find("road[@id='1']")
    objects=west.find('objects')
    ET.SubElement(objects,'object',{'id':'413201','name':'business_frontage','type':'building',
        's':'380','t':'-12','zOffset':'0','hdg':'0','length':'12','width':'8','height':'5','orientation':'none'})
    ET.SubElement(objects,'object',{'id':'413202','name':'freight_loading_zone','type':'roadMark',
        's':'385','t':'-10','zOffset':'.01','hdg':'0','length':'10','width':'2','height':'0','orientation':'none'})
    return ET.tostring(root,encoding='unicode')


def route(case):
    points=[(-70.0+i,-1.75) for i in range(59)]
    a,b,c,d=(-11.,-1.75),(-4.,-1.75),(1.75,-4.),(1.75,-11.)
    for i in range(1,81):
        t=i/80;u=1-t
        points.append((u**3*a[0]+3*u*u*t*b[0]+3*u*t*t*c[0]+t**3*d[0],
                       u**3*a[1]+3*u*u*t*b[1]+3*u*t*t*c[1]+t**3*d[1]))
    points += [(1.75,-11.-i) for i in range(1,60)]
    return points


def static_check():
    root=ET.fromstring(build_xodr())
    assert len(root.findall('road'))>=4
    west=root.find("road[@id='1']")
    assert west.find('lanes/laneSection/right/lane[@id="-1"]') is not None
    names={o.attrib['name'] for o in west.findall('objects/object')}
    assert {'business_frontage','freight_loading_zone'}<=names
    p=route(None)
    assert p[0][0]<-60 and p[-1][1]<-60
    assert all(abs(x)<=7 or abs(y)<=7 for x,y in p)
    return {'roads':len(root.findall('road')),'frontage_objects':sorted(names),'route_points':len(p)}
