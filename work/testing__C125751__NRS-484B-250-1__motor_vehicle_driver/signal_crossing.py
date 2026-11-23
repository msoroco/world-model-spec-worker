"""Source-bound median-opening construction preflight and fail-closed controller.

CARLA remains an injected runtime dependency; this module is CPU importable.
"""
from __future__ import annotations

import hashlib
import math


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _xy(point):
    return (float(point[0]), float(point[1]))


def _inside(point, box):
    x, y = _xy(point)
    x0, y0, x1, y1 = map(float, box)
    return x0 <= x <= x1 and y0 <= y <= y1


def validate_source_packet(packet: dict, map_bytes: bytes, review_bytes: bytes):
    """Reject unsourced crossing, road, device and driver facts before spawning."""
    if packet.get('schema') != 'median-signal-review-v1':
        raise ValueError('unreviewed packet schema')
    if packet.get('map_sha256') != sha256(map_bytes):
        raise ValueError('map source hash mismatch')
    if packet.get('review_sha256') != sha256(review_bytes):
        raise ValueError('roadway and device review hash mismatch')
    if packet.get('cell_id') != 'C125751' or packet.get('law_id') != 'NRS-484B-250-1':
        raise ValueError('wrong cell or law')
    if packet.get('driver_scope_reviewed') is not True:
        raise ValueError('conventional driver scope not reviewed')
    if packet.get('crossing_id') is None or not packet.get('official_device_inventory'):
        raise ValueError('crossing/device inventory absent')
    if packet.get('ego_highway') == packet.get('other_highway'):
        raise ValueError('different-highway premise not established')
    box = packet.get('crossing_bounds_xy_m')
    if not isinstance(box, list) or len(box) != 4 or box[0] >= box[2] or box[1] >= box[3]:
        raise ValueError('crossing bounds invalid')
    for party in ('ego', 'other'):
        route = packet.get(f'{party}_route_xy_m')
        if not isinstance(route, list) or len(route) < 3:
            raise ValueError(f'{party} route incomplete')
        if _inside(route[0], box) or _inside(route[-1], box) or not any(_inside(p, box) for p in route[1:-1]):
            raise ValueError(f'{party} route misses declared crossing')
        if not isinstance(packet.get(f'{party}_road_id'), int):
            raise ValueError(f'{party} road ID absent')
    a = [_xy(p) for p in (packet['ego_route_xy_m'][0], packet['ego_route_xy_m'][1])]
    b = [_xy(p) for p in (packet['other_route_xy_m'][0], packet['other_route_xy_m'][1])]
    v = (a[1][0]-a[0][0], a[1][1]-a[0][1])
    w = (b[1][0]-b[0][0], b[1][1]-b[0][1])
    nv, nw = math.hypot(*v), math.hypot(*w)
    if not nv or not nw or abs((v[0]*w[0]+v[1]*w[1])/(nv*nw)) > 0.5:
        raise ValueError('not distinct crossing approaches')
    return packet


def bind_native(world_map, packet: dict, location_factory):
    """Map binding requires exact OpenDRIVE bytes, road IDs and junction reach."""
    if sha256(world_map.to_opendrive().encode()) != packet['map_sha256']:
        raise ValueError('live map differs from reviewed OpenDRIVE')
    routes = {}
    for party in ('ego', 'other'):
        waypoints = []
        for x, y in packet[f'{party}_route_xy_m']:
            wp = world_map.get_waypoint(location_factory(x, y), project_to_road=False)
            if wp is None or math.hypot(wp.transform.location.x-x, wp.transform.location.y-y) > 2:
                raise ValueError(f'{party} route off live lane')
            waypoints.append(wp)
        if waypoints[0].road_id != packet[f'{party}_road_id']:
            raise ValueError(f'{party} approach road differs')
        if not any(w.is_junction for w in waypoints[1:-1]):
            raise ValueError(f'{party} route lacks junction')
        for first, second in zip(waypoints, waypoints[1:]):
            if not _forward_connected(first, second):
                raise ValueError(f'{party} route disconnected')
        routes[party] = waypoints
    return routes


def construct_native(world, packet: dict, map_bytes: bytes, review_bytes: bytes,
                     location_factory, resolve_device, spawn_vehicle):
    """Validate both Native routes and the live device before actor allocation."""
    validate_source_packet(packet, map_bytes, review_bytes)
    routes = bind_native(world.get_map(), packet, location_factory)
    device_id = packet['official_device_inventory'][0].get('id')
    if not device_id:
        raise ValueError('reviewed device ID missing')
    live_device = resolve_device(world, packet['official_device_inventory'][0])
    if live_device is None or not hasattr(live_device, 'get_state'):
        raise ValueError('reviewed device absent in Native world')
    state = str(live_device.get_state()).split('.')[-1]
    if state not in {'Red', 'Yellow', 'Green'}:
        raise ValueError('live device state unreadable')
    actors = {}
    for party in ('ego', 'other'):
        actor = spawn_vehicle(party, routes[party][0].transform)
        if actor is None:
            raise ValueError(f'{party} spawn failed')
        actors[party] = actor
    return {'routes': routes, 'actors': actors, 'device': live_device,
            'initial_light_readback': state}


def _forward_connected(first, second):
    pending, seen = [first], set()
    for index in range(1200):
        if index >= len(pending):
            break
        wp = pending[index]
        p = wp.transform.location
        key = (wp.road_id, wp.lane_id, round(p.x, 1), round(p.y, 1))
        if key in seen:
            continue
        seen.add(key)
        target = second.transform.location
        if index and wp.road_id == second.road_id and wp.lane_id == second.lane_id and math.hypot(p.x-target.x, p.y-target.y) <= 2:
            return True
        pending.extend(wp.next(2.0))
    return False


def controller_request(ego_before: bool, other_entered: bool, other_cleared: bool,
                       light_readback: str | None, fresh: bool, require_other_first=True):
    """Engineering action only; the official-device exception is not adjudicated."""
    if not fresh or light_readback not in {'Red', 'Yellow', 'Green'}:
        return 'brake'
    if light_readback in {'Red', 'Yellow'}:
        return 'brake'
    if ego_before and require_other_first and (not other_entered or not other_cleared):
        return 'brake'
    return 'proceed'
