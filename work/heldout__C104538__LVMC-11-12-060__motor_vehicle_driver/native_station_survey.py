"""Verify an operator-supplied station scene against the live Native CARLA map.

No station is asserted by this package. An operator must provide an independently
reviewed station manifest at execution through CARLA_FIRE_STATION_SURVEY.
"""
from hashlib import sha256
import json
import math
import os
from pathlib import Path

from fire_station_geometry import validate_entrance

BRANCHES = ('front_of_entrance','front_of_approach','through_driveway','remote_reference')

def _coordinate(transform):
    return {'x':float(transform.location.x),'y':float(transform.location.y),
            'z':float(transform.location.z),'yaw':float(transform.rotation.yaw)}

def _near(actual, expected, tolerance):
    return all(math.isfinite(actual[k]) and abs(actual[k]-float(expected[k]))<=tolerance[k]
               for k in ('x','y','z','yaw'))

def _waypoint(world_map, ref):
    wp=world_map.get_waypoint_xodr(int(ref['road_id']),int(ref['lane_id']),float(ref['s']))
    if wp is None:raise ValueError('Operator station waypoint absent from Native map')
    return wp

def verify(world, world_map, document, raw_sha256):
    if (document.get('format')!='worker-native-fire-station-survey-v1' or
            document.get('map_name')!=world_map.name or
            document.get('opendrive_sha256')!=sha256(world_map.to_opendrive().encode('utf-8')).hexdigest()):
        raise ValueError('Operator station survey differs from Native map/OpenDRIVE')
    identity=document.get('station_object',{})
    if (not document.get('reviewer') or not document.get('evidence_reference') or
            document.get('verified_fire_station') is not True or
            type(identity.get('id')) is not int or not identity.get('name') or
            not identity.get('type') or not isinstance(identity.get('transform'),dict)):
        raise ValueError('Operator-reviewed station identity is incomplete')
    objects=[obj for obj in world.get_environment_objects() if obj.id==identity['id']]
    if len(objects)!=1:
        raise ValueError('Operator station object absent or ambiguous in Native scene')
    obj=objects[0]
    actual=_coordinate(obj.transform)
    if (obj.name!=identity['name'] or str(obj.type)!=identity['type'] or
            not _near(actual,identity['transform'],{'x':.05,'y':.05,'z':.05,'yaw':.1})):
        raise ValueError('Operator station object identity or transform changed')
    survey=document.get('station_survey',{})
    anchors={key:_waypoint(world_map,survey[key]) for key in
             ('public_before','public_at','public_after','driveway_at')}
    source={'kind':'operator_survey','asset_id':f"environment:{obj.id}:{obj.name}",
            'source_sha256':raw_sha256}
    geometry=validate_entrance(anchors['public_before'],anchors['public_at'],
                               anchors['public_after'],anchors['driveway_at'],source=source)
    routes=survey.get('routes',{})
    if set(routes)!=set(BRANCHES):
        raise ValueError('Operator station survey omits an exact route')
    for branch in BRANCHES:
        refs=routes[branch]
        if not isinstance(refs,list) or len(refs)<3:
            raise ValueError('Operator station route is incomplete: '+branch)
        waypoints=[_waypoint(world_map,ref) for ref in refs]
        if len({(wp.road_id,wp.lane_id,round(wp.s,2)) for wp in waypoints})<3:
            raise ValueError('Operator station route lacks distinct map waypoints')
        if branch=='through_driveway' and not any(
                (wp.road_id,wp.lane_id)==(anchors['driveway_at'].road_id,anchors['driveway_at'].lane_id)
                for wp in waypoints):
            raise ValueError('Operator driveway route omits driveway lane')
    verified=dict(survey,map_name=world_map.name,station_source=source)
    receipt={'format':'worker-native-fire-station-verification-v1','verified':True,
             'map_name':world_map.name,'opendrive_sha256':document['opendrive_sha256'],
             'operator_manifest_sha256':raw_sha256,'operator_reviewer':document['reviewer'],
             'station_object':dict(identity,actual_transform=actual),
             'station_source':source,
             'branch_angle_deg':geometry['branch_angle_deg'],
             'public_lane':list(geometry['public_lane']),
             'driveway_lane':list(geometry['driveway_lane']),
             'routes_verified':list(BRANCHES),
             'physical_station_identity_claimed_by_package':False}
    return verified,receipt

def load_and_verify(world, world_map, output):
    filename=os.environ.get('CARLA_FIRE_STATION_SURVEY')
    if not filename:raise ValueError('CARLA_FIRE_STATION_SURVEY operator manifest required at Native execution')
    path=Path(filename)
    raw=path.read_bytes(); digest=sha256(raw).hexdigest()
    document=json.loads(raw)
    survey,receipt=verify(world,world_map,document,digest)
    output=Path(output)
    original=output/'station-survey-original.json'
    verified=output/'station-survey-verification.json'
    if original.exists() or verified.exists():
        raise ValueError('Retain prior Native station survey sources')
    original.write_bytes(raw)
    verified.write_text(json.dumps(receipt,indent=2)+'\n')
    return survey,receipt
