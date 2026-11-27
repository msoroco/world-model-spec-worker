"""Fail-closed original Engineer-permission, marking and lawful-direction review."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
ASSIGNMENT='testing__C377875__LVMC-11-52-070__motor_vehicle_driver'
SOURCE_NAMES=('map','roadway','marking','authority','vehicle','purpose')

def point(v):
    if not isinstance(v,list) or len(v)!=2 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in v):
        raise ValueError('finite two-coordinate point required')
    return float(v[0]),float(v[1])

def inside(p,vertices):
    if not isinstance(vertices,list) or len(vertices)<3:raise ValueError('permission extent polygon required')
    poly=[point(x) for x in vertices];x,y=p;hit=False
    for a,b in zip(poly,poly[1:]+poly[:1]):
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:hit=not hit
    return hit

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def unit(v):
    x,y=point(v);length=math.hypot(x,y)
    if length<.01:raise ValueError('lawful traffic direction vector required')
    return x/length,y/length

def load_site(path,case_id):
    path=Path(path).resolve();site=json.loads(path.read_text())
    if site.get('assignment_id')!=ASSIGNMENT or site.get('case_id')!=case_id or not case_id.startswith(ASSIGNMENT+'__'):
        raise ValueError('wrong exact Engineer-angle-parking assignment or case')
    suffix=case_id.rsplit('__',1)[-1]
    try:activity,orientation=suffix.split('_',1)
    except ValueError as e:raise ValueError('unsupported exact case') from e
    if activity not in {'stand','park'} or orientation not in {'forward','opposing'}:
        raise ValueError('unsupported exact stand/park orientation')
    if site.get('requested_activity')!=activity or site.get('requested_orientation')!=orientation:
        raise ValueError('reviewed site differs from exact case request')
    refs=site.get('sources',{})
    if not isinstance(refs,dict) or set(SOURCE_NAMES)-set(refs):raise ValueError('all original source packets required')
    records={}
    for name in SOURCE_NAMES:
        ref=refs[name];rel=ref.get('path') if isinstance(ref,dict) else None
        if not isinstance(rel,str) or Path(rel).is_absolute() or '..' in Path(rel).parts:
            raise ValueError('contained relative original source path required: '+name)
        target=(path.parent/rel).resolve()
        if not target.is_relative_to(path.parent) or not target.is_file() or sha(target)!=ref.get('sha256'):
            raise ValueError('original source missing or changed: '+name)
        records[name]=json.loads(target.read_text())
    road=records['roadway'];authority=records['authority'];marking=records['marking']
    if road.get('district')!='business' or road.get('highway_status')!='reviewed_original' or road.get('jurisdiction')!='city':
        raise ValueError('original city business-district street review required')
    lawful=unit(road.get('lawful_traffic_vector_xy'))
    if road.get('lawful_direction_status')!='reviewed_original':
        raise ValueError('original lawful traffic movement direction required')
    if authority.get('determining_office')!='City Traffic Engineer' or authority.get('permission_status')!='reviewed_original' or authority.get('angle_parking_permitted') is not True or not authority.get('source'):
        raise ValueError('original Engineer determination and permission required')
    if marking.get('marking_status')!='reviewed_original' or not marking.get('content_review') or marking.get('permission_indicated') is not True:
        raise ValueError('original sign or marking indicating permitted angle parking required')
    if not inside(point(site.get('target_xy')),authority.get('permission_extent_polygon_xy')):
        raise ValueError('target outside reviewed permission extent')
    if not inside(point(site.get('target_xy')),marking.get('governed_space_polygon_xy')):
        raise ValueError('target outside reviewed marking extent')
    if math.dist(point(site.get('target_xy')),point(site.get('approach_xy')))<8:
        raise ValueError('construction approach too short')
    if records['purpose'].get('activity_review')!='reviewed_original' or records['purpose'].get('category')!=activity:
        raise ValueError('original stand/park purpose and service review required')
    if not records['vehicle'].get('source') or records['vehicle'].get('front_direction_status')!='reviewed_original':
        raise ValueError('original vehicle/front identification required')
    if not isinstance(records['map'].get('opendrive_sha256'),str) or len(records['map']['opendrive_sha256'])!=64:
        raise ValueError('original OpenDRIVE source required')
    if not isinstance(site.get('map_id'),str) or not isinstance(site.get('road_id'),int) or not site.get('vehicle_blueprint_id'):
        raise ValueError('Native map, road and vehicle identity required')
    if not marking.get('prop_blueprint_id') or not isinstance(marking.get('prop_pose'),dict):
        raise ValueError('reviewed marking prop construction required')
    pose=marking['prop_pose']
    if any(isinstance(pose.get(k),bool) or not isinstance(pose.get(k),(int,float)) or not math.isfinite(pose[k]) for k in ('x','y','z','yaw_deg')):
        raise ValueError('finite marking prop pose required')
    for key in ('approach_heading_degrees','target_heading_degrees'):
        value=site.get(key)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('finite '+key+' required')
    heading=math.radians(site['target_heading_degrees'])
    dot=math.cos(heading)*lawful[0]+math.sin(heading)*lawful[1]
    if orientation=='forward' and dot<.95:raise ValueError('target front not constructed toward lawful traffic')
    if orientation=='opposing' and dot>-.95:raise ValueError('target front not constructed opposing lawful traffic')
    return site,records
