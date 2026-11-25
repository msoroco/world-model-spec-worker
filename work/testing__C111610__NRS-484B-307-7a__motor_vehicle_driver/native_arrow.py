"""Source-gated flashing-yellow-arrow turn construction and original-event measurement.

The surveyed site and event history are original Native inputs. A synthetic CPU
fixture checks the logic, never supplies a lawful-presence or legal verdict.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

class ArrowError(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise ArrowError(message)

def original(ref, root):
    base=Path(root).resolve()
    path=(base/ref['path']).resolve()
    require(path.is_relative_to(base), 'source escapes attempt')
    require(path.is_file(), 'original source missing')
    require(hashlib.sha256(path.read_bytes()).hexdigest()==ref['sha256'], 'original source hash mismatch')
    return path

def in_polygon(point, polygon):
    x,y=map(float,point)
    inside=False
    for i,(x1,y1) in enumerate(polygon):
        x2,y2=polygon[(i+1)%len(polygon)]
        cross=(x-x1)*(y2-y1)-(y-y1)*(x2-x1)
        if abs(cross)<1e-8 and min(x1,x2)-1e-8<=x<=max(x1,x2)+1e-8 and min(y1,y2)-1e-8<=y<=max(y1,y2)+1e-8:
            return True
        if (y1>y)!=(y2>y) and x<x1+(y-y1)*(x2-x1)/(y2-y1):
            inside=not inside
    return inside

def verify_site(site, root):
    require(site['cell_id']=='C111610' and site['actor']=='motor_vehicle_driver', 'wrong site')
    refs=site['original_sources']
    paths={r['path'] for r in refs}
    for field in ('map_source_path','signal_source_path','route_source_path','crosswalk_source_path'):
        require(site[field] in paths, 'unbound site source: '+field)
    for ref in refs:
        original(ref,root)
    require(site['native_map_name'] and site['official_head_id'] and site['ego_approach_id'], 'map/signal identity missing')
    require(site['facing_relation'] is True, 'arrow not facing ego approach')
    require(site['arrow_movement'] in ('left','right'), 'turn arrow movement missing')
    route=site['ego_route_xy']
    require(len(route)>=3 and all(len(p)==2 and all(math.isfinite(float(v)) for v in p) for p in route), 'invalid turn route')
    for field in ('intersection_polygon_xy','adjacent_crosswalk_polygon_xy'):
        poly=site[field]
        require(len(poly)>=3 and all(len(p)==2 and all(math.isfinite(float(v)) for v in p) for p in poly), 'invalid '+field)
    require(not in_polygon(route[0],site['intersection_polygon_xy']), 'ego starts in intersection')
    require(any(in_polygon(p,site['intersection_polygon_xy']) for p in route[1:-1]), 'route misses intersection')
    a,b,c=route[0],route[len(route)//2],route[-1]
    cross=(b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0])
    require(abs(cross)>1.0, 'route has no turn geometry')
    require((cross>0)==(site['arrow_movement']=='left'), 'route disagrees with arrow direction')
    if str(site.get('case_id', '')).endswith('__arrow_concurrent_movement'):
        require(site.get('concurrent_route_source_path') in paths,
                'concurrent movement route source missing')
        concurrent=site.get('concurrent_route_xy')
        require(isinstance(concurrent,list) and len(concurrent)>=3 and
                all(len(p)==2 and all(math.isfinite(float(v)) for v in p) for p in concurrent),
                'concurrent movement route missing')
        require(concurrent[0]==route[0] and
                not in_polygon(concurrent[0],site['intersection_polygon_xy']) and
                any(in_polygon(p,site['intersection_polygon_xy']) for p in concurrent[1:-1]),
                'concurrent movement route lacks same approach and intersection entry')
        a,b,c=concurrent[0],concurrent[len(concurrent)//2],concurrent[-1]
        other_cross=(b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0])
        require(abs(other_cross)<1e-8 and concurrent!=route,
                'concurrent movement needs a distinct through route')
        route_ref=next(r for r in refs if r['path']==site['concurrent_route_source_path'])
        require(json.loads(original(route_ref,root).read_text()).get('route_xy')==concurrent,
                'concurrent movement route source differs from surveyed route')
    return True

def construct_native(site, root, world, carla, ego_blueprint, other_blueprint=None, other_kind=None):
    """CARLA-lazy source-surveyed spawn; caller owns actors after success."""
    verify_site(site,root)
    native_map=world.get_map()
    require(native_map.name==site['native_map_name'], 'map readback mismatch')
    routes=[site['ego_route_xy']]
    if str(site.get('case_id','')).endswith('__arrow_concurrent_movement'):
        routes.append(site['concurrent_route_xy'])
    for route in routes:
        for xy in route:
            waypoint=native_map.get_waypoint(carla.Location(x=float(xy[0]),y=float(xy[1]),z=0))
            require(waypoint is not None, 'surveyed route absent from Native map')
            location=waypoint.transform.location
            require(math.hypot(location.x-xy[0],location.y-xy[1])<=2,
                    'surveyed route differs from Native map')
    crosswalks=native_map.get_crosswalks()
    require(crosswalks and sum(in_polygon([v.x,v.y],site['adjacent_crosswalk_polygon_xy'])
                                for v in crosswalks)>=4,
            'surveyed adjacent crosswalk absent from Native map')
    heads={str(h.id):h for h in world.get_actors().filter('traffic.traffic_light*')}
    require(str(site['official_head_id']) in heads, 'official head missing')
    require(site['signal_source_mode']=='native_head_plus_external_aspect_packet', 'signal adapter declaration missing')
    def pose(xy,yaw):
        return carla.Transform(carla.Location(x=float(xy[0]),y=float(xy[1]),z=float(site['spawn_z_m'])),carla.Rotation(yaw=float(yaw)))
    ego=world.try_spawn_actor(ego_blueprint,pose(site['ego_route_xy'][0],site['ego_yaw_deg']))
    require(ego is not None, 'ego spawn failed')
    spawned=[ego]
    try:
        if other_kind:
            require(other_kind in ('pedestrian','motor_vehicle'), 'unsupported participant')
            require(other_blueprint is not None, 'participant blueprint missing')
            other=world.try_spawn_actor(other_blueprint,pose(site['other_spawn_xy'],site['other_yaw_deg']))
            require(other is not None, 'participant spawn failed')
            spawned.append(other)
        selected_route=(site['concurrent_route_xy'] if
            str(site.get('case_id', '')).endswith('__arrow_concurrent_movement')
            else site['ego_route_xy'])
        return {'actors':spawned,'route_xy':selected_route,'official_head_id':site['official_head_id'],'map_name':site['native_map_name']}
    except Exception:
        for actor in reversed(spawned):
            actor.destroy()
        raise

def measure_original(site, root, event_ref):
    verify_site(site,root)
    events=json.loads(original(event_ref,root).read_text())
    require(isinstance(events,list) and len(events)>=3, 'original event history missing')
    last=-1; measured=[]; arrow_states=[]
    for row in events:
        frame=row['frame']
        require(isinstance(frame,int) and frame>last, 'frame order invalid')
        last=frame
        require(str(row['official_head_id'])==str(site['official_head_id']), 'head identity changed')
        require(row['facing_approach_id']==site['ego_approach_id'], 'facing relation changed')
        aspects=row['lit_aspects']
        require(isinstance(aspects,list), 'original aspect inventory missing')
        arrow_states.append('flashing_yellow_turn_arrow' in aspects)
        require(row['arrow_movement']==site['arrow_movement'], 'arrow movement changed')
        require(row['ego_movement'] and row['ego_movement'] in (site['arrow_movement'],row.get('concurrently_permitted_movement')), 'unbound movement')
        users=[]
        for user in row['other_users']:
            require(user['kind'] in ('pedestrian','motor_vehicle') and user['id'], 'participant classification missing')
            require(user.get('lawful_presence_source'), 'external lawful-presence source missing')
            region='intersection' if in_polygon(user['xy'],site['intersection_polygon_xy']) else 'adjacent_crosswalk' if in_polygon(user['xy'],site['adjacent_crosswalk_polygon_xy']) else 'outside'
            users.append({'id':user['id'],'kind':user['kind'],'region':region,'lawful_presence_source':user['lawful_presence_source']})
        measured.append({'frame':frame,'lit_aspects':aspects,'arrow_lit':arrow_states[-1],'ego_xy':row['ego_xy'],'ego_in_intersection':in_polygon(row['ego_xy'],site['intersection_polygon_xy']),'ego_movement':row['ego_movement'],'other_users':users})
    transitions=sum(a!=b for a,b in zip(arrow_states,arrow_states[1:]))
    require(any(arrow_states) and not all(arrow_states) and transitions>=2, 'flashing arrow transitions missing')
    require(not measured[0]['ego_in_intersection'] and any(r['ego_in_intersection'] for r in measured), 'no measured intersection entry')
    return {'frame_count':len(measured),'arrow_transitions':transitions,'records':measured,'original_sources':[event_ref]+site['original_sources'],'lawful_presence_verdict':None,'cautious_entry_verdict':None,'right_of_way_verdict':None}
