"""C110741 authored crosswalk and two reverse paths; CPU only."""
from __future__ import annotations
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
CROSSWALK = (-19.0, -3.5, -15.0, 3.5)
INTERSECTION = (-7.0, -7.0, 7.0, 7.0)
START_X = -10.0
STOPS = {"condition_a": -11.0, "condition_b": -14.0}
Y_M = -1.75


def road_xml():
    return (HERE/'road.xodr').read_text()


def body(x, y=Y_M):
    return [[round(x+dx,5),round(y+dy,5)] for dx,dy in
            ((-2.6,-1.1),(-2.6,1.1),(2.6,1.1),(2.6,-1.1))]


def overlap(vertices, region):
    xs=[v[0] for v in vertices];ys=[v[1] for v in vertices]
    return max(0,min(max(xs),region[2])-max(min(xs),region[0]))*\
           max(0,min(max(ys),region[3])-max(min(ys),region[1]))


def route(suffix):
    if suffix not in STOPS:raise ValueError('Unknown controlled reverse path')
    n=round((START_X-STOPS[suffix])/.05)
    return [[round(START_X-i*.05,5),Y_M] for i in range(n+1)]


def check():
    root=ET.fromstring((HERE/'road.xodr').read_text())
    objects=root.findall(".//object[@type='crosswalk']")
    if len(objects)!=1 or objects[0].attrib['name']!='C110741-marked-crosswalk':
        raise ValueError('Authored crosswalk object missing')
    if len(root.findall('junction/connection'))!=2:
        raise ValueError('Same-cell intersection topology differs')
    if overlap(body(START_X),CROSSWALK) or overlap(body(START_X),INTERSECTION):
        raise ValueError('Common start footprint touches prohibited feature')
    outcomes={}
    for suffix in STOPS:
        points=route(suffix)
        if any(a[0]-b[0] != .05 for a,b in zip(points,points[1:])):
            # Floating-point representation is compared at the centimeter scale.
            if any(abs(a[0]-b[0]-.05)>1e-8 for a,b in zip(points,points[1:])):
                raise ValueError('Reverse path discontinuity')
        footprint=body(points[-1][0])
        cross=overlap(footprint,CROSSWALK)
        intersection=overlap(footprint,INTERSECTION)
        if intersection:
            raise ValueError('Crosswalk branch confounded by intersection overlap')
        if (suffix=='condition_a' and cross) or (suffix=='condition_b' and cross<3):
            raise ValueError('Controlled reverse-crosswalk distinction differs')
        outcomes[suffix]={'stop_center_xy_m':points[-1],
                          'crosswalk_overlap_m2':round(cross,5),
                          'intersection_overlap_m2':round(intersection,5),
                          'reverse_path_points':len(points)}
    return {'passed':True,'scope':'authored OpenDRIVE crosswalk object and prospective body only',
            'law_id':'NRS-484B-113-2','cell_id':'C110741',
            'comparison_variable':'reverse_path_overlap',
            'native_or_legal_outcome_claimed':False,'cases':outcomes}


if __name__=='__main__':print(json.dumps(check(),indent=2))
