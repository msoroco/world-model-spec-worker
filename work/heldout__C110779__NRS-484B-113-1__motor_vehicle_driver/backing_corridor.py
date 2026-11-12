"""Validate an operator-reviewed Native intersection backing corridor."""
from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path


def _point(value):
    if not isinstance(value, list) or len(value) != 2 or any(type(x) not in (int, float) or not isfinite(x) for x in value):
        raise ValueError('Native backing corridor needs finite XY points')
    return tuple(float(x) for x in value)


def _inside(point, polygon):
    x, y = point
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        x1, y1 = a; x2, y2 = b
        if (y1 > y) != (y2 > y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1:
            inside = not inside
    return inside


def verify(world_map, path, ego_heading_xy):
    path = Path(path)
    raw = path.read_bytes()
    source = json.loads(raw)
    if (source.get('format') != 'worker-native-backing-corridor-v1' or
            source.get('verified_intersection') is not True or
            not source.get('reviewer') or not source.get('evidence_reference') or
            not source.get('other_vehicle_purpose')):
        raise ValueError('Reviewed Native backing corridor identity is absent')
    if source.get('map_name') != world_map.name or source.get('opendrive_sha256') != sha256(world_map.to_opendrive().encode()).hexdigest():
        raise ValueError('Native backing corridor map/OpenDRIVE differs')
    polygon = [_point(p) for p in source['intersection_polygon_xy']]
    if len(polygon) < 3:
        raise ValueError('Intersection polygon is incomplete')
    start, end, other = [_point(source[key]) for key in ('start_xy', 'end_xy', 'other_vehicle_xy')]
    if not all(_inside(point, polygon) for point in (start, end)):
        raise ValueError('Reverse path leaves reviewed intersection corridor')
    if not _inside(other, polygon):
        raise ValueError('Other traffic actor is outside reviewed intersection context')
    heading = _point(list(ego_heading_xy));norm=hypot(*heading)
    length=hypot(end[0]-start[0],end[1]-start[1])
    if norm < .5 or length < 5 or length > 25 or ((end[0]-start[0])*heading[0]+(end[1]-start[1])*heading[1])/norm > -4:
        raise ValueError('Selected corridor does not construct a bounded reverse route')
    for key in ('other_vehicle_road_id', 'other_vehicle_lane_id'):
        if type(source.get(key)) is not int:
            raise ValueError('Other vehicle needs a sourced Native road/lane identity')
    return {'format':'worker-native-backing-corridor-verification',
            'source_sha256':sha256(raw).hexdigest(),'map_name':world_map.name,
            'opendrive_sha256':source['opendrive_sha256'],
            'start_xy':start,'end_xy':end,'other_vehicle_xy':other,
            'other_vehicle_purpose':source['other_vehicle_purpose'],
            'other_vehicle_road_id':source['other_vehicle_road_id'],
            'other_vehicle_lane_id':source['other_vehicle_lane_id'],
            'reviewer':source['reviewer'],'evidence_reference':source['evidence_reference'],
            'physical_motion_claimed':False,'legal_safety_claimed':False}
