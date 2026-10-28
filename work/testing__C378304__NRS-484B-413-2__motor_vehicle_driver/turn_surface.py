"""Executable draft U-turn road and full polygon occupancy checks."""
import math

def build_uturn():
    # Right-side 7 m lanes: center travels radius 13.5 m, not reference radius 10 m.
    def road(ident,length,x,y,heading,geometry,pre,suc):
        link=''
        if pre is not None:link+='<predecessor elementType="road" elementId="%s" contactPoint="end"/>'%pre
        if suc is not None:link+='<successor elementType="road" elementId="%s" contactPoint="start"/>'%suc
        return '<road name="uturn-%s" length="%s" id="%s" junction="-1"><link>%s</link><planView><geometry s="0" x="%s" y="%s" hdg="%s" length="%s">%s</geometry></planView><elevationProfile/><lateralProfile/><lanes><laneSection s="0"><center><lane id="0" type="none" level="false"/></center><right><lane id="-1" type="driving" level="false"><link><predecessor id="-1"/><successor id="-1"/></link><width sOffset="0" a="7" b="0" c="0" d="0"/></lane></right></laneSection></lanes></road>'%(ident,length,ident,link,x,y,heading,length,geometry)
    return '<?xml version="1.0"?><OpenDRIVE><header revMajor="1" revMinor="4" name="uturn-draft" version="1" date="2026-10-27" north="0" south="0" east="0" west="0"/>'+road(1,200,0,0,0,'<line/>',None,2)+road(2,math.pi*10,200,0,0,'<arc curvature="0.1"/>',1,3)+road(3,200,200,20,math.pi,'<line/>',2,None)+'</OpenDRIVE>'

def uturn_route():
    approach=[(float(x),-3.5) for x in range(20,201,2)]
    arc=[(200+13.5*math.sin(t),10-13.5*math.cos(t)) for t in [i*math.pi/100 for i in range(1,101)]]
    exit_path=[(float(x),23.5) for x in range(198,19,-2)]
    return approach+arc+exit_path

def orientation(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])

def polygons_overlap(a,b):
    # Separating axis theorem for convex polygons, including rotated footprint.
    for polygon in (a,b):
        for p,q in zip(polygon,polygon[1:]+polygon[:1]):
            nx,ny=-(q[1]-p[1]),q[0]-p[0]
            pa=[nx*v[0]+ny*v[1] for v in a];pb=[nx*v[0]+ny*v[1] for v in b]
            if max(pa)<min(pb) or max(pb)<min(pa):return False
    return True

def validate_comparison(branch,footprint,divider):
    occupied=polygons_overlap(footprint,divider)
    return {'requested_branch':branch,'median_overlap':occupied,'method':'convex polygon separating axis theorem; world-space footprint vertices','public_authority_established':None}
