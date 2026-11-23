"""Source-bound district and freight-zone context for a right-turn route.

This checks that authored geometry and review records are internally consistent.
A Native run must still confirm the actual zone, frontage and visible signs.
"""
import hashlib
import math
from pathlib import Path


def _xy(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError('Missing planar site point')
    point = (float(value[0]), float(value[1]))
    if not all(math.isfinite(v) for v in point):
        raise ValueError('Nonfinite site point')
    return point


def _document(root, record, label):
    if not isinstance(record, dict) or not record.get('path') or not record.get('sha256') or not record.get('reviewer') or not record.get('review_method'):
        raise ValueError('Unsourced '+label+' context')
    root = Path(root).resolve()
    path = (root / record['path']).resolve()
    if root not in path.parents or not path.is_file():
        raise ValueError('Missing '+label+' source document')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != record['sha256']:
        raise ValueError('Changed '+label+' source document')
    return digest


def _point_segment_distance(point, a, b):
    vx, vy = b[0]-a[0], b[1]-a[1]
    length2 = vx*vx+vy*vy
    if length2 == 0:
        return math.dist(point,a)
    t = max(0.0,min(1.0,((point[0]-a[0])*vx+(point[1]-a[1])*vy)/length2))
    return math.dist(point,(a[0]+t*vx,a[1]+t*vy))


def _cross(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def _intersects(a,b,c,d):
    return (max(min(a[0],b[0]),min(c[0],d[0])) <= min(max(a[0],b[0]),max(c[0],d[0])) and
            max(min(a[1],b[1]),min(c[1],d[1])) <= min(max(a[1],b[1]),max(c[1],d[1])) and
            _cross(a,b,c)*_cross(a,b,d) <= 0 and _cross(c,d,a)*_cross(c,d,b) <= 0)


def _inside(point, polygon):
    x,y=point
    inside=False
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        if (a[1]>y)!=(b[1]>y):
            x_edge=a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1])
            if x<x_edge:inside=not inside
    return inside


def route_zone_distance(route_points, polygon):
    route=[_xy(p) for p in route_points]
    zone=[_xy(p) for p in polygon]
    if len(route)<2 or len(zone)<3:
        raise ValueError('Incomplete route or freight-zone geometry')
    area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(zone,zone[1:]+zone[:1]))/2
    if abs(area)<0.01:
        raise ValueError('Degenerate freight-zone polygon')
    if any(_inside(p,zone) for p in route):
        return 0.0
    edges=list(zip(zone,zone[1:]+zone[:1]))
    segments=list(zip(route,route[1:]))
    if any(_intersects(a,b,c,d) for a,b in segments for c,d in edges):
        return 0.0
    return min([_point_segment_distance(p,a,b) for p in zone for a,b in segments]+
               [_point_segment_distance(p,a,b) for p in route for a,b in edges])


def validate_site(packet, route, source_root):
    """Bind a reviewed district and designated zone to one realized route."""
    if not isinstance(packet,dict) or not isinstance(route,dict):
        raise ValueError('Missing route/site context')
    district=packet.get('district',{})
    zone=packet.get('freight_loading_zone',{})
    if district.get('type') not in ('business','residential','other'):
        raise ValueError('District class not sourced')
    if not district.get('frontage_facts') or not district.get('building_use_facts'):
        raise ValueError('District frontage/building use omitted')
    district_sha=_document(source_root,district.get('source'),'district')
    if zone.get('designation') != 'freight_loading_zone' or not zone.get('marking_or_sign_evidence'):
        raise ValueError('Freight loading zone designation unverified')
    zone_sha=_document(source_root,zone.get('source'),'freight-zone')
    if zone['source']['path']==district['source']['path']:
        raise ValueError('District and zone need independent source records')
    if zone.get('road_id') != route.get('approach_road_id'):
        raise ValueError('Freight zone belongs to another road')
    if packet.get('native_map_id') != route.get('native_map_id'):
        raise ValueError('Site and Native route map identities differ')
    points=route.get('approach_points_xy_m',[])+route.get('outgoing_points_xy_m',[])
    distance=route_zone_distance(points,zone.get('polygon_xy_m',[]))
    clearance=float(zone.get('minimum_centerline_clearance_m',0))
    adjacency=float(zone.get('maximum_route_distance_m',0))
    if not all(math.isfinite(x) and x>0 for x in (clearance,adjacency)) or clearance>=adjacency:
        raise ValueError('Freight-zone clearance/adjacency contract invalid')
    if distance<clearance or distance>adjacency:
        raise ValueError('Freight zone intrudes on route or is unrelated to it')
    return {'district_type':district['type'],'district_source_sha256':district_sha,
            'freight_zone_source_sha256':zone_sha,'route_zone_distance_m':distance,
            'native_map_id':packet['native_map_id'],
            'physical_acceptance_claimed':False}
