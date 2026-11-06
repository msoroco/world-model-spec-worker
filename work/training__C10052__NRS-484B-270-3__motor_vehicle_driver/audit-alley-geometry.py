"""Independent source and body-sweep audit of the proposed Native alley turn."""
import hashlib
import json
import math
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

from audit_geometry import clipped_area

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from alley_geometry import open_drive,route


def audit():
    root=ET.fromstring(open_drive())
    roads={int(road.get('id')):road for road in root.findall('road')}
    assert set(roads)=={1,2}
    lane=roads[1].find("lanes/laneSection/right/lane[@id='-2']")
    assert lane.get('type')=='biking'
    assert float(roads[2].find('planView/geometry').get('x'))==1.5
    paths=[route(-45.0),route(-55.0)]
    assert paths[0][0]==(-45,-1.5) and paths[0][-1]==(0,-12)
    assert paths[1][0]==(-55,-1.5) and paths[1][-1]==(0,-12)
    assert paths[0]==paths[1][100:]
    facility=(-60,-5,60,-3);alley=(-3,-14,3,-5)
    counts=[]
    for points in paths:
        hits=[0,0,0]
        for left,right in zip(points,points[1:]):
            dx=right[0]-left[0];dy=right[1]-left[1]
            distance=math.hypot(dx,dy)
            assert 0<distance<=.102
            fx,fy=dx/distance,dy/distance
            shape=[(left[0]+long*fx-side*fy,left[1]+long*fy+side*fx)
                   for long,side in ((-2.6,-.9),(-2.6,.9),(2.6,.9),(2.6,-.9))]
            f=clipped_area(shape,facility)>.01
            a=clipped_area(shape,alley)>.01
            hits[0]+=f;hits[1]+=a;hits[2]+=f and a
        assert all(value>0 for value in hits)
        counts.append(hits)
    assert counts[0]==counts[1]
    return {'passed':True,'route_points':[len(path) for path in paths],
        'common_tail_points':len(paths[0]),'body_overlap_counts':counts[0],
        'native_connector_identity_verified':False,
        'physical_behavior_claimed':False,
        'source_sha256':hashlib.sha256((HERE/'native/alley_geometry.py').read_bytes()).hexdigest()}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
