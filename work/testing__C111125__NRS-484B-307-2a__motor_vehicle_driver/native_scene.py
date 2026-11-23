"""Source-gated straight green intersection construction and original-event measurement.

The site is a surveyed Native packet. This module does not synthesize a signal
phase, a lawful-presence determination, or a right-of-way verdict.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

class SourceError(ValueError):
    pass

def require(ok, message):
    if not ok:
        raise SourceError(message)

def source(ref, root):
    base = Path(root).resolve()
    path = (base / ref['path']).resolve()
    require(path.is_relative_to(base), 'source escapes attempt root')
    require(path.is_file(), 'missing original source: ' + ref['path'])
    require(hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256'], 'source hash mismatch: ' + ref['path'])
    return path

def inside(point, polygon):
    """Boundary-inclusive ray casting for a surveyed planar region."""
    x, y = map(float, point)
    flag = False
    for i, (x1, y1) in enumerate(polygon):
        x2, y2 = polygon[(i + 1) % len(polygon)]
        cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
        if abs(cross) < 1e-8 and min(x1, x2)-1e-8 <= x <= max(x1, x2)+1e-8 and min(y1, y2)-1e-8 <= y <= max(y1, y2)+1e-8:
            return True
        if (y1 > y) != (y2 > y) and x < x1 + (y-y1)*(x2-x1)/(y2-y1):
            flag = not flag
    return flag

def verify_site(site, root):
    require(site['cell_id'] == 'C111125' and site['actor'] == 'motor_vehicle_driver', 'assignment site mismatch')
    refs = site['original_sources']
    for key in ('map_source_path', 'signal_source_path', 'route_source_path', 'crosswalk_source_path'):
        require(site[key] in [r['path'] for r in refs], 'missing site source binding: ' + key)
    for ref in refs:
        source(ref, root)
    require(site['official_head_id'] and site['ego_approach_id'], 'official facing signal identity required')
    require(site['facing_relation'] is True, 'signal does not govern ego approach')
    route = site['ego_route_xy']
    require(len(route) >= 3, 'straight route needs at least three points')
    for p in route:
        require(len(p) == 2 and all(math.isfinite(float(v)) for v in p), 'nonfinite route point')
    x0,y0=route[0]; x1,y1=route[-1]
    dx,dy=x1-x0,y1-y0
    require(dx*dx+dy*dy > 1, 'route too short')
    # Surveyed straight cell: all route points stay near approach-to-exit chord.
    for x,y in route[1:-1]:
        require(abs((x-x0)*dy-(y-y0)*dx)/math.hypot(dx,dy) < site['straight_tolerance_m'], 'route turns outside straight cell')
    for key in ('intersection_polygon_xy','adjacent_crosswalk_polygon_xy'):
        poly=site[key]
        require(len(poly)>=3 and all(len(p)==2 and all(math.isfinite(float(v)) for v in p) for p in poly), 'invalid surveyed polygon: '+key)
    require(any(inside(p,site['intersection_polygon_xy']) for p in route[1:-1]), 'route misses surveyed intersection')
    return True

def measure_attempt(site, root, event_ref):
    """Bind green exhibition, positions at that instant, and later conflict timing."""
    verify_site(site,root)
    events=json.loads(source(event_ref,root).read_text())
    require(isinstance(events,list) and len(events)>=3, 'original frame history required')
    prev=-1; exhibition=None; green_frames=0; records=[]
    for row in events:
        frame=row['frame']
        require(isinstance(frame,int) and frame>prev, 'frame order invalid')
        prev=frame
        require(row['official_head_id']==site['official_head_id'], 'signal identity changed')
        require(row['facing_approach_id']==site['ego_approach_id'], 'facing approach changed')
        aspects=row['lit_aspects']
        require(isinstance(aspects,list), 'original signal aspects required')
        green=aspects==['circular_green']
        green_frames+=int(green)
        ego_in=inside(row['ego_xy'],site['intersection_polygon_xy'])
        participants=[]
        for person in row['other_users']:
            require(person['kind'] in ('motor_vehicle','pedestrian'), 'unclassified other user')
            require(person['id'] and 'lawful_presence_source' in person, 'user identity/lawful-presence source missing')
            region='intersection' if inside(person['xy'],site['intersection_polygon_xy']) else 'adjacent_crosswalk' if inside(person['xy'],site['adjacent_crosswalk_polygon_xy']) else 'outside'
            participants.append({'id':person['id'],'kind':person['kind'],'region':region,'lawful_presence_source':person['lawful_presence_source']})
        if green and exhibition is None:
            exhibition={'frame':frame,'ego_in_intersection':ego_in,'other_users':participants}
        records.append({'frame':frame,'circular_green_alone':green,'ego_in_intersection':ego_in,'other_users':participants})
    require(exhibition is not None, 'no original circular-green-alone exhibition')
    require(not records[0]['ego_in_intersection'], 'ego already in intersection at start')
    require(any(r['ego_in_intersection'] for r in records), 'ego never enters intersection')
    return {'exhibition':exhibition,'green_frames':green_frames,'frame_count':len(records),'records':records,'original_sources':[event_ref]+site['original_sources'],'lawful_presence_verdict':None,'right_of_way_verdict':None}

def construct_native(site, root, world, carla, ego_blueprint, other_blueprint=None, other_kind=None):
    """Spawn source-surveyed actors after Native map/signal readback.

    world and carla are injected to permit a no-CARLA CPU proof. The caller owns
    resulting actors and must destroy them in a guaranteed cleanup path.
    """
    verify_site(site,root)
    require(world.get_map().name == site['native_map_name'], 'Native map readback mismatch')
    heads={a.id:a for a in world.get_actors().filter('traffic.traffic_light*')}
    require(site['official_head_id'] in heads, 'official signal head absent')
    require(heads[site['official_head_id']].get_state().name == 'Green', 'official head readback is not green')
    require(site['initial_lit_aspects']==['circular_green'], 'sole circular green source packet missing')
    def transform(xy):
        return carla.Transform(carla.Location(x=float(xy[0]),y=float(xy[1]),z=float(site['spawn_z_m'])),carla.Rotation(yaw=float(site['approach_yaw_deg'])))
    ego=world.try_spawn_actor(ego_blueprint,transform(site['ego_route_xy'][0]))
    require(ego is not None, 'ego spawn failed')
    spawned=[ego]
    try:
        if other_kind is not None:
            require(other_kind in ('motor_vehicle','pedestrian'), 'unsupported other user kind')
            require(other_blueprint is not None, 'other user blueprint missing')
            where=site['other_user_spawn_xy']
            other=world.try_spawn_actor(other_blueprint,transform(where))
            require(other is not None, 'other user spawn failed')
            spawned.append(other)
        return {'actors':spawned,'ego_route_xy':site['ego_route_xy'],'official_head_id':site['official_head_id'],'map_name':site['native_map_name'],'other_kind':other_kind}
    except Exception:
        for actor in reversed(spawned):
            actor.destroy()
        raise
