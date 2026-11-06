"""C110812 controlled reverse around a street corner, prospective CPU geometry."""
from __future__ import annotations
import json,math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
INTERSECTION=(-7.,-7.,7.,7.)
CROSSWALK=(-19.,-3.5,-15.,3.5)
START=(12.,-1.75,0.)
ARC_START=(8.,-1.75)
ARC_CENTER=(8.,4.5)
RADIUS=6.25
ARC_LENGTH=RADIUS*math.pi/2
TOTAL_REVERSE_DISTANCE=4+ARC_LENGTH

def road_xml():return (HERE/'road.xodr').read_text()
def body(x,y,yaw_deg):
    a=math.radians(yaw_deg);ca=math.cos(a);sa=math.sin(a)
    return [[round(x+dx*ca-dy*sa,5),round(y+dx*sa+dy*ca,5)]
            for dx,dy in ((-2.6,-1.1),(-2.6,1.1),(2.6,1.1),(2.6,-1.1))]
def overlap(vertices,box):
    polygon=[tuple(v) for v in vertices]
    for axis,bound,keep_high in ((0,box[0],True),(0,box[2],False),
                                 (1,box[1],True),(1,box[3],False)):
        if not polygon:return 0.0
        previous=polygon[-1];clipped=[]
        for current in polygon:
            prev_inside=previous[axis]>=bound if keep_high else previous[axis]<=bound
            curr_inside=current[axis]>=bound if keep_high else current[axis]<=bound
            if prev_inside!=curr_inside:
                t=(bound-previous[axis])/(current[axis]-previous[axis])
                clipped.append((previous[0]+t*(current[0]-previous[0]),
                                previous[1]+t*(current[1]-previous[1])))
            if curr_inside:clipped.append(current)
            previous=current
        polygon=clipped
    return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in
                   zip(polygon,polygon[1:]+polygon[:1])))/2
def pose(suffix,fraction):
    if suffix not in ('condition_a','condition_b'):raise ValueError('Unknown controlled case')
    if not 0<=fraction<=1:raise ValueError('Invalid reverse progress')
    distance=TOTAL_REVERSE_DISTANCE*fraction
    if suffix=='condition_a':return (12-distance,-1.75,0.)
    if distance<=4:return (12-distance,-1.75,0.)
    angle=(distance-4)/RADIUS
    return (ARC_CENTER[0]-RADIUS*math.sin(angle),
            ARC_CENTER[1]-RADIUS*math.cos(angle),
            -math.degrees(angle))
def route(suffix):
    return [pose(suffix,i/200) for i in range(201)]
def check():
    root=ET.fromstring(road_xml())
    if len(root.findall('junction/connection'))!=2:
        raise ValueError('Authored junction differs')
    objects=root.findall(".//object[@type='crosswalk']")
    if len(objects)!=1 or objects[0].attrib.get('name')!='C110812-west-crosswalk':
        raise ValueError('Authored crosswalk context differs')
    if overlap(body(*START),INTERSECTION) or overlap(body(*START),CROSSWALK):
        raise ValueError('Common start touches prohibited geometry')
    outcomes={}
    for suffix in ('condition_a','condition_b'):
        path=route(suffix)
        max_cross=max(overlap(body(*p),CROSSWALK) for p in path)
        if max_cross:raise ValueError('Corner branch confounded by crosswalk')
        turning_frames=sum(abs(path[i][2]-path[i-1][2])>.01 for i in range(1,len(path)))
        junction=max(overlap(body(*p),INTERSECTION) for p in path)
        if junction<=0:raise ValueError('Intersection context absent')
        if (suffix=='condition_a' and turning_frames) or (suffix=='condition_b' and turning_frames<50):
            raise ValueError('Corner-turn distinction differs')
        outcomes[suffix]={'end_pose_xy_yaw':list(path[-1]),
                          'reverse_distance_m':TOTAL_REVERSE_DISTANCE,
                          'corner_turning_frames':turning_frames,
                          'heading_change_deg':abs(path[-1][2]-path[0][2]),
                          'max_intersection_overlap_m2':junction,
                          'max_crosswalk_overlap_m2':max_cross}
    return {'passed':True,'cell_id':'C110812','law_id':'NRS-484B-113-2',
            'scope':'authored prospective route and body only; no physical or legal outcome',
            'comparison_variable':'backing_around_street_corner',
            'cases':outcomes}
if __name__=='__main__':print(json.dumps(check(),indent=2))
