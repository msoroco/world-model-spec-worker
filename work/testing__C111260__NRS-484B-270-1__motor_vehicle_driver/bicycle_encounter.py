"""Source-gated bicycle encounter construction and original-history measurement.

Geometric conflict and commanded behavior are observations, never legal verdicts
about lawful riding, intention, or interference under NRS 484B.270(1).
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from rider_sources import verify_inventory, KINDS

ASSIGNMENT = 'testing__C111260__NRS-484B-270-1__motor_vehicle_driver'
MODES = ('maintain_clearance', 'cross_rider_path')

class SourceError(ValueError):
    pass

def require(ok, why):
    if not ok:
        raise SourceError(why)

def read_source(ref, root):
    base = Path(root).resolve()
    p = (base / ref['path']).resolve()
    require(p.is_relative_to(base) and p.is_file(), 'missing or escaping original source: ' + ref['path'])
    require(hashlib.sha256(p.read_bytes()).hexdigest() == ref['sha256'], 'original source hash mismatch: ' + ref['path'])
    return p

def segment_intersection(a,b,c,d):
    """Return crossing point for non-parallel 2-D segments, or None."""
    ax,ay=map(float,a); bx,by=map(float,b); cx,cy=map(float,c); dx,dy=map(float,d)
    r=(bx-ax,by-ay); s=(dx-cx,dy-cy)
    den=r[0]*s[1]-r[1]*s[0]
    if abs(den)<1e-9:
        return None
    q=(cx-ax,cy-ay)
    t=(q[0]*s[1]-q[1]*s[0])/den
    u=(q[0]*r[1]-q[1]*r[0])/den
    return (ax+t*r[0],ay+t*r[1]) if 0<=t<=1 and 0<=u<=1 else None

def verify_site(site, root):
    require(site['assignment_id']==ASSIGNMENT and site['cell_id']=='C111260', 'assignment/cell mismatch')
    require(site['layout']=='intersection' and site['maneuver']=='travel' and site['control']=='cyclist', 'fixed catalog mismatch')
    refs=site['original_sources']
    require(len(refs)>=3 and len({r['path'] for r in refs})==len(refs), 'map, bicycle and rider-rule sources required')
    source_paths={r['path']:read_source(r,root) for r in refs}
    paths=set(source_paths)
    for key in ('map_source_path','bicycle_classification_source_path','rider_rules_source_path'):
        require(site[key] in paths, 'unbound site source: '+key)
    require(site.get('rider_inventory_source_path') in paths,
            'source-bound rider inventory missing')
    rider_kind = site.get('rider_kind')
    require(rider_kind in KINDS, 'rider kind missing')
    inventory_ref = next(ref for ref in refs if ref['path'] == site['rider_inventory_source_path'])
    inventory = verify_inventory(root, inventory_ref, assignment_id=ASSIGNMENT,
                                 cell_id='C111260', blueprint_id=site['bicycle_blueprint_id'],
                                 rider_kind=rider_kind)
    map_packet=json.loads(source_paths[site['map_source_path']].read_text())
    bicycle_packet=json.loads(source_paths[site['bicycle_classification_source_path']].read_text())
    rider_rules_packet=json.loads(source_paths[site['rider_rules_source_path']].read_text())
    require(map_packet.get('native_map_name')==site['native_map_name'] and map_packet.get('ego_route_xy')==site['ego_route_xy'] and map_packet.get('rider_route_xy')==site['rider_route_xy'], 'surveyed map/route packet mismatch')
    if 'native_opendrive' in map_packet:
        raw = map_packet['native_opendrive']
        require(raw in refs and raw['path'] in source_paths, 'surveyed Native map source unbound')
        readbacks = map_packet.get('waypoint_readbacks', {})
        limit = float(map_packet.get('max_waypoint_snap_m', 0))
        require(math.isfinite(limit) and 0 < limit <= 2, 'surveyed waypoint limit invalid')
        for role, route_key in (('ego', 'ego_route_xy'), ('rider', 'rider_route_xy')):
            samples = readbacks.get(role, [])
            require(len(samples) == len(site[route_key]), 'surveyed waypoint count mismatch')
            for sample, point in zip(samples, site[route_key]):
                require(sample['requested_xy'] == point, 'surveyed requested point mismatch')
                snap = math.dist(point, sample['native_waypoint_xy'])
                require(math.isfinite(snap) and snap <= limit and abs(snap - sample['snap_m']) < 1e-6, 'surveyed waypoint readback mismatch')
                require(isinstance(sample['road_id'], int) and isinstance(sample['lane_id'], int), 'surveyed road/lane missing')
        require(any(sample['is_junction'] for samples in readbacks.values() for sample in samples), 'surveyed junction readback missing')
    require(bicycle_packet.get('blueprint_id')==site['bicycle_blueprint_id'] and bicycle_packet.get('classification')==site['bicycle_classification'], 'bicycle classification packet mismatch')
    require(rider_rules_packet.get('applicable_rules') and rider_rules_packet.get('jurisdiction')==site['jurisdiction'], 'rider rules/jurisdiction packet mismatch')
    require(site['native_map_name'] and site['ego_blueprint_id'] and site['bicycle_blueprint_id'], 'map/blueprint identity missing')
    require(site['bicycle_classification'] == inventory['device_observations'],
            'device classification differs from reviewed inventory')
    require(rider_rules_packet['applicable_rules'] ==
            inventory['rules_observations']['applicable_rules'],
            'rider rule list differs from reviewed inventory')
    for key in ('ego_route_xy','rider_route_xy'):
        route=site[key]
        require(len(route)>=2, 'route too short: '+key)
        require(all(len(p)==2 and all(math.isfinite(float(v)) for v in p) for p in route), 'nonfinite route: '+key)
    crossings=[segment_intersection(a,b,c,d) for a,b in zip(site['ego_route_xy'],site['ego_route_xy'][1:]) for c,d in zip(site['rider_route_xy'],site['rider_route_xy'][1:])]
    require(any(x is not None for x in crossings), 'surveyed routes never intersect')
    require(site['rider_actor_id'] and site['rider_actor_id']!=site['ego_actor_id'], 'distinct actors required')
    return [x for x in crossings if x is not None]

def construct_native(site, root, world, carla, mode):
    """Spawn source-surveyed motor vehicle and bicycle using an injected CARLA API.

    Caller owns returned actors; on a partial spawn this function cleans up.
    """
    require(mode in MODES, 'unknown encounter mode')
    crossings=verify_site(site,root)
    require(world.get_map().name==site['native_map_name'], 'Native map readback mismatch')
    library=world.get_blueprint_library()
    ego_bp=library.find(site['ego_blueprint_id'])
    bike_bp=library.find(site['bicycle_blueprint_id'])
    require(ego_bp.id==site['ego_blueprint_id'] and bike_bp.id==site['bicycle_blueprint_id'], 'Native blueprint readback mismatch')
    def transform(route,yaw):
        x,y=route[0]
        return carla.Transform(carla.Location(x=float(x),y=float(y),z=float(site['spawn_z_m'])),carla.Rotation(yaw=float(yaw)))
    ego=world.try_spawn_actor(ego_bp,transform(site['ego_route_xy'],site['ego_yaw_deg']))
    require(ego is not None, 'ego spawn failed')
    actors=[ego]
    try:
        bike=world.try_spawn_actor(bike_bp,transform(site['rider_route_xy'],site['rider_yaw_deg']))
        require(bike is not None, 'bicycle spawn failed')
        actors.append(bike)
        require(ego.type_id==site['ego_blueprint_id'] and bike.type_id==site['bicycle_blueprint_id'], 'spawned actor blueprint readback mismatch')
        return {'actors':actors,'mode':mode,'rider_kind':site['rider_kind'],'crossings_xy':crossings,'ego_route_xy':site['ego_route_xy'],'rider_route_xy':site['rider_route_xy'],'rider_rule_verdict':None,'intent_verdict':None}
    except Exception:
        for actor in reversed(actors):
            actor.destroy()
        raise

def measure_attempt(site, root, event_ref, mode):
    """Measure uninterrupted 20 Hz Original poses and explicit control commands."""
    require(mode in MODES, 'unknown encounter mode')
    crossings=verify_site(site,root)
    events=json.loads(read_source(event_ref,root).read_text())
    require(isinstance(events,list) and len(events)>=3, 'original event history required')
    previous=-1; records=[]
    for row in events:
        frame=row['frame']
        require(isinstance(frame,int) and (frame==previous+1 if previous>=0 else frame>=0), 'noncontinuous Original frames')
        previous=frame
        require(row['ego_id']==site['ego_actor_id'] and row['rider_id']==site['rider_actor_id'], 'actor identity changed')
        require(row['ego_blueprint_id']==site['ego_blueprint_id'] and row['rider_blueprint_id']==site['bicycle_blueprint_id'], 'actor type changed')
        require(row['mode_command']==mode and row['command_source'] in ('controller_log','human_input_log'), 'command source/mode missing')
        require(row['rider_visual_present'] in (True,False), 'rider visual readback missing')
        for key in ('ego_xy','rider_xy'):
            require(len(row[key])==2 and all(math.isfinite(float(v)) for v in row[key]), 'nonfinite pose: '+key)
        gap=math.dist(row['ego_xy'],row['rider_xy'])
        records.append({'frame':frame,'ego_xy':row['ego_xy'],'rider_xy':row['rider_xy'],'center_gap_m':gap,'rider_visual_present':row['rider_visual_present'],'mode_command':mode})
    require(any(r['rider_visual_present'] for r in records), 'no original visual rider presence')
    return {'mode':mode,'rider_kind':site['rider_kind'],'frame_count':len(records),'minimum_center_gap_m':min(r['center_gap_m'] for r in records),'crossings_xy':crossings,'records':records,'original_sources':site['original_sources']+[event_ref],'lawful_riding_verdict':None,'intent_verdict':None,'interference_verdict':None}
