"""Proposed C10052 road-to-alley turn, pending Native connector readback."""
import json
import math
import xml.etree.ElementTree as ET

from geometry import body, open_drive as base_open_drive
from measure_facility import overlap_area


def open_drive():
    root=ET.fromstring(base_open_drive())
    # Shift the southbound road's reference line so its right driving-lane
    # center is x=0, the tangent point of the five-meter turn.
    south=root.find("road[@id='2']/planView/geometry")
    south.set('x','1.5')
    return ET.tostring(root,encoding='unicode')


def route(start_x=-45.0):
    if start_x not in (-45.0,-55.0):raise ValueError('Unknown approach start')
    points=[]
    count=round((-5-start_x)/.1)
    for i in range(count+1):
        points.append((round(start_x+i*.1,6),-1.5))
    radius=5.0
    arc_length=math.pi*radius/2
    for i in range(1,round(arc_length/.1)+1):
        fraction=i/round(arc_length/.1)
        theta=math.pi/2*(1-fraction)
        points.append((round(-5+radius*math.cos(theta),6),
                       round(-6.5+radius*math.sin(theta),6)))
    for i in range(1,56):
        points.append((0.0,round(-6.5-i*.1,6)))
    return points


def check():
    root=ET.fromstring(open_drive())
    assert root.find("road[@id='1']/lanes/laneSection/right/lane[@id='-2']").get('type')=='biking'
    assert root.find("road[@id='2']/planView/geometry").get('x')=='1.5'
    points=route()
    assert points[0]==(-45.0,-1.5) and points[-1]==(0.0,-12.0)
    assert route(-55.0)[0]==(-55.0,-1.5)
    assert max(math.dist(a,b) for a,b in zip(points,points[1:]))<.102
    facility=(-60,-5,60,-3);alley=(-3,-14,3,-5)
    # Prospective body is aligned to the local route tangent.
    facility_frames=alley_frames=both_frames=0
    for i,center in enumerate(points[:-1]):
        next_point=points[i+1]
        dx=next_point[0]-center[0];dy=next_point[1]-center[1]
        scale=math.hypot(dx,dy)
        shape=body(*center,forward=(dx/scale,dy/scale))
        in_facility=overlap_area(shape,facility)>.01
        in_alley=overlap_area(shape,alley)>.01
        facility_frames+=in_facility;alley_frames+=in_alley;both_frames+=in_facility and in_alley
    assert facility_frames>0 and alley_frames>0 and both_frames>0
    return {'format':'c10052-alley-native-geometry-proposal-v1',
        'route_points':len(points),'radius_m':5.0,
        'prospective_facility_body_samples':facility_frames,
        'prospective_alley_body_samples':alley_frames,
        'prospective_simultaneous_body_samples':both_frames,
        'native_connector_identity_verified':False,
        'physical_behavior_claimed':False}


if __name__=='__main__':print(json.dumps(check(),indent=2))
