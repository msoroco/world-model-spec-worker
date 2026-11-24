"""C110763 authored intersection-entry backing pair; prospective CPU geometry."""
from __future__ import annotations
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
INTERSECTION=(-7.0,-7.0,7.0,7.0)
START_X=12.0
STOPS={'condition_a':10.0,'condition_b':8.0}
Y_M=-1.75

def road_xml():return (HERE/'road.xodr').read_text()
def body(x,y=Y_M):
    return [[round(x+dx,5),round(y+dy,5)] for dx,dy in
            ((-2.6,-1.1),(-2.6,1.1),(2.6,1.1),(2.6,-1.1))]
def overlap(vertices,region):
    xs=[v[0] for v in vertices];ys=[v[1] for v in vertices]
    return max(0,min(max(xs),region[2])-max(min(xs),region[0]))*max(0,min(max(ys),region[3])-max(min(ys),region[1]))
def route(suffix):
    if suffix not in STOPS:raise ValueError('Unknown controlled reverse path')
    n=round((START_X-STOPS[suffix])/.05)
    return [[round(START_X-i*.05,5),Y_M] for i in range(n+1)]
def check():
    root=ET.fromstring(road_xml())
    if len(root.findall('junction/connection'))!=2 or root.findall(".//object[@type='crosswalk']"):
        raise ValueError('Same-cell unmarked intersection topology differs')
    if overlap(body(START_X),INTERSECTION):raise ValueError('Start body enters junction')
    outcomes={}
    for suffix in STOPS:
        points=route(suffix)
        if any(abs(a[0]-b[0]-.05)>1e-8 for a,b in zip(points,points[1:])):
            raise ValueError('Reverse path discontinuity')
        area=overlap(body(points[-1][0]),INTERSECTION)
        if (suffix=='condition_a' and area) or (suffix=='condition_b' and area<3):
            raise ValueError('Controlled intersection-entry distinction differs')
        outcomes[suffix]={'stop_center_xy_m':points[-1],
                          'intersection_overlap_m2':round(area,5),
                          'reverse_path_points':len(points)}
    return {'passed':True,'scope':'authored OpenDRIVE junction and prospective body only',
            'law_id':'NRS-484B-113-2','cell_id':'C110763',
            'comparison_variable':'reverse_path_intersection_occupancy',
            'native_or_legal_outcome_claimed':False,'cases':outcomes}
if __name__=='__main__':print(json.dumps(check(),indent=2))
