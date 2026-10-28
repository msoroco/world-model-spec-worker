"""Two carriageways, an authored median opening, and full-body divider survey."""
import math
import xml.etree.ElementTree as ET


def road(ident,length,x,y,heading,geometry,pre=None,suc=None,objects=''):
    links=''
    if pre is not None:links+='<predecessor elementType="road" elementId="%s" contactPoint="end"/>'%pre
    if suc is not None:links+='<successor elementType="road" elementId="%s" contactPoint="start"/>'%suc
    return ('<road name="median-%s" length="%s" id="%s" junction="-1"><link>%s</link>'
      '<planView><geometry s="0" x="%s" y="%s" hdg="%s" length="%s">%s</geometry></planView>'
      '<elevationProfile/><lateralProfile/><lanes><laneSection s="0"><center><lane id="0" type="none" level="false"/>'
      '</center><right><lane id="-1" type="driving" level="false"><link><predecessor id="-1"/><successor id="-1"/></link>'
      '<width sOffset="0" a="7" b="0" c="0" d="0"/></lane></right></laneSection></lanes><objects>%s</objects></road>')%(
      ident,length,ident,links,x,y,heading,length,geometry,objects)


def build_xodr():
    # A 30m opening is centered at x=205. Barrier segments are authored as
    # distinct objects; their actual generated surfaces/collision remain a
    # mandatory live survey, not a static acceptance claim.
    left='<object id="227101" name="intact_median_west" type="barrier" s="95" t="10" zOffset="0" hdg="0" length="190" width="1" height="1" orientation="none"/>'
    right='<object id="227102" name="intact_median_east" type="barrier" s="90" t="10" zOffset="0" hdg="0" length="180" width="1" height="1" orientation="none"/>'
    return ('<OpenDRIVE><header revMajor="1" revMinor="4" name="C126120-median-opening" version="1" date="2026-10-27" north="30" south="-10" east="400" west="0"/>'+
        road(1,200,0,0,0,'<line/>',None,2,left)+
        road(2,math.pi*10,200,0,0,'<arc curvature="0.1"/>',1,3)+
        road(3,200,200,20,math.pi,'<line/>',2,None)+
        road(4,180,220,0,0,'<line/>',None,None,right)+
        road(5,180,400,20,math.pi,'<line/>')+
        '</OpenDRIVE>')


def route(case):
    branch=case['variable_assignments']['test_branch']['value']
    center=150 if branch=='u_turn_divider' else 200
    approach=[(float(x),-3.5) for x in range(20,center+1)]
    arc=[(center+13.5*math.sin(t),10-13.5*math.cos(t)) for t in [i*math.pi/100 for i in range(1,101)]]
    exit_path=[(float(x),23.5) for x in range(center-1,19,-1)]
    return approach+arc+exit_path


def median_status(vertices):
    # Conservative AABB occupancy; all original native vertices are retained
    # for exact polygon checks in saved analysis.
    xs=[v[0] for v in vertices];ys=[v[1] for v in vertices]
    overlaps_median=min(ys)<20 and max(ys)>0
    overlaps_intact=overlaps_median and (min(xs)<190 or max(xs)>220)
    overlaps_opening=overlaps_median and min(xs)>=190 and max(xs)<=220
    return {'median_overlap':overlaps_median,'intact_divider_overlap':overlaps_intact,
            'wholly_within_opening_x':overlaps_opening}


def static_check():
    root=ET.fromstring(build_xodr())
    assert len(root.findall('road'))==5
    objects={o.attrib['name'] for o in root.findall('.//object')}
    assert objects=={'intact_median_west','intact_median_east'}
    class Case:
        variable_assignments={}
    for branch in ('u_turn_opening','u_turn_divider','u_turn_opening_multiple'):
        case={'variable_assignments':{'test_branch':{'value':branch}}}
        points=route(case)
        assert len(points)>250
        assert all(math.dist(a,b)<=1.5 for a,b in zip(points,points[1:]))
    return {'carriageways':2,'connector_roads':1,'authored_barrier_segments':2,
            'opening_x_m':[190,220]}
