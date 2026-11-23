"""Source-bound bus intersection construction and original-frame device measurements.

Engineering measurements only: official placement, police authority, and NRS 484B.307
applicability are original-source questions, never inferred from a fixture label.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

class SourceError(ValueError):
    pass

def need(ok, message):
    if not ok:
        raise SourceError(message)

def sealed(root, ref):
    base = Path(root).resolve()
    path = (base / ref['path']).resolve()
    need(path.is_relative_to(base) and path.is_file(), 'missing or escaped source: ' + ref['path'])
    need(hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256'], 'source hash mismatch: ' + ref['path'])
    return path

def _point(p):
    need(len(p) == 2 and all(math.isfinite(float(x)) for x in p), 'invalid point')
    return float(p[0]), float(p[1])

def validate_site(site, root):
    need(site['cell_id'] == 'C111329' and site['actor'] == 'bus_driver', 'wrong assignment identity')
    need(site['native_map_name'] and site['device_id'] and site['ego_approach_id'], 'missing map, device or approach identity')
    refs = site['original_sources']
    for key in ('map_source_path', 'device_source_path', 'route_source_path', 'authority_source_path'):
        need(site[key] in {r['path'] for r in refs}, 'unbound source: ' + key)
    for ref in refs:
        sealed(root, ref)
    route = [_point(p) for p in site['bus_route_xy']]
    need(len(route) >= 3, 'connected bus route needs three points')
    need(sum(math.dist(a,b) for a,b in zip(route,route[1:])) > 10, 'bus route too short')
    need(site['governs_ego_approach'] is True, 'device not shown governing bus approach')
    _point(site['stop_line_xy'])
    need(site['bus_clearance_width_m'] > site['bus_body_width_m'] > 0, 'bus clearance insufficient')
    need(site['bus_clearance_height_m'] > site['bus_body_height_m'] > 0, 'bus height clearance insufficient')
    return True

def construct_native(site, root, world, carla, bus_blueprint):
    """Create the source-surveyed bus; caller owns and destroys the returned actor."""
    validate_site(site, root)
    need(world.get_map().name == site['native_map_name'], 'Native map readback mismatch')
    heads = {a.id:a for a in world.get_actors().filter('traffic.traffic_light*')}
    need(site['device_id'] in heads, 'surveyed device absent in Native world')
    need(bus_blueprint.id == site['bus_blueprint_id'], 'bus blueprint mismatch')
    x,y = site['bus_route_xy'][0]
    transform = carla.Transform(carla.Location(x=float(x), y=float(y), z=float(site['spawn_z_m'])), carla.Rotation(yaw=float(site['approach_yaw_deg'])))
    bus = world.try_spawn_actor(bus_blueprint, transform)
    need(bus is not None, 'bus spawn failed')
    try:
        need(bus.type_id == site['bus_blueprint_id'], 'spawned actor is not surveyed bus type')
        return {'bus':bus, 'route_xy':site['bus_route_xy'], 'device_id':site['device_id'], 'map_name':site['native_map_name']}
    except Exception:
        bus.destroy()
        raise

def signed_distance_to_stop(site, xy):
    """Positive before the line, negative after, on the surveyed route axis."""
    route = site['bus_route_xy']
    a = _point(route[0]); b = _point(route[-1]); line = _point(site['stop_line_xy']); p = _point(xy)
    dx,dy = b[0]-a[0],b[1]-a[1]
    n = math.hypot(dx,dy)
    need(n > 0, 'zero route axis')
    return ((line[0]-p[0])*dx + (line[1]-p[1])*dy)/n

def measure_attempt(site, root, event_ref):
    validate_site(site, root)
    events = json.loads(sealed(root, event_ref).read_text())
    need(isinstance(events,list) and len(events) >= 3, 'original frame history required')
    prev = -1; rows=[]; first_entry = None
    for event in events:
        frame = event['frame']
        need(isinstance(frame,int) and frame > prev, 'nonmonotone original frames')
        prev = frame
        need(event['device_id'] == site['device_id'] and event['facing_approach_id'] == site['ego_approach_id'], 'device identity/governance changed')
        need(event['bus_actor_id'] and event['bus_blueprint_id'] == site['bus_blueprint_id'], 'bus source identity changed')
        need(event['aspect'] in ('red','yellow','green'), 'unrecognized observed aspect')
        need('police_direction_source' in event and 'placement_source' in event and 'nrs_307_context_source' in event, 'missing exception/provenance source')
        distance = signed_distance_to_stop(site,event['bus_front_xy'])
        row = {'frame':frame,'aspect':event['aspect'],'bus_front_signed_distance_m':distance,
               'police_direction':event['police_direction'],'police_direction_source':event['police_direction_source'],
               'placement_source':event['placement_source'],'nrs_307_context_source':event['nrs_307_context_source']}
        rows.append(row)
        if first_entry is None and distance < 0:
            first_entry = row
    need(rows[0]['bus_front_signed_distance_m'] > 0, 'bus already past stop line at first frame')
    return {'frames':rows,'first_line_entry':first_entry,'source_refs':site['original_sources']+[event_ref],
            'official_placement_verdict':None,'police_authority_verdict':None,'nrs_307_exception_verdict':None,'legal_compliance_verdict':None}
