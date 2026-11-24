"""Seal a Native map and waypoint survey for the C111260 bicycle encounter.

This is an acquisition step, not proof of rider classification, conduct or law.
The caller provides proposed routes; every point must have a close Native waypoint
readback on the loaded map before the packet can be used by verify_site.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from bicycle_encounter import ASSIGNMENT, SourceError, require, segment_intersection


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return {'path': path.name, 'sha256': _sha(path)}


def survey(world, carla, requested, output_dir):
    """Write original OpenDRIVE and route packet; return their relative hash refs.

    CARLA is injected and never imported here. Run this only in an execution
    output directory (normally .runtime-work), not in the frozen runtime tree.
    """
    require(requested.get('assignment_id') == ASSIGNMENT and requested.get('cell_id') == 'C111260', 'assignment/cell mismatch')
    require(requested.get('layout') == 'intersection' and requested.get('maneuver') == 'travel' and requested.get('control') == 'cyclist', 'catalog mismatch')
    map_obj = world.get_map()
    name = map_obj.name
    require(isinstance(name, str) and name, 'Native map name missing')
    xodr = map_obj.to_opendrive()
    require(isinstance(xodr, str) and len(xodr) > 10, 'Native OpenDRIVE missing')
    snap_limit = float(requested.get('max_waypoint_snap_m', 1.5))
    require(math.isfinite(snap_limit) and 0 < snap_limit <= 2, 'invalid waypoint snap limit')
    routes = {}
    readbacks = {}
    for role, key in (('ego', 'ego_route_xy'), ('rider', 'rider_route_xy')):
        route = requested.get(key)
        require(isinstance(route, list) and len(route) >= 2, role + ' route missing')
        points = []
        samples = []
        for raw in route:
            require(isinstance(raw, list) and len(raw) == 2, role + ' point malformed')
            xy = [float(raw[0]), float(raw[1])]
            require(all(math.isfinite(v) for v in xy), role + ' point nonfinite')
            wp = map_obj.get_waypoint(carla.Location(x=xy[0], y=xy[1], z=0.0), project_to_road=True)
            require(wp is not None, role + ' waypoint missing')
            loc = wp.transform.location
            native_xy = [float(loc.x), float(loc.y)]
            require(all(math.isfinite(v) for v in native_xy), role + ' waypoint nonfinite')
            snap = math.dist(xy, native_xy)
            require(snap <= snap_limit, role + ' waypoint snap exceeds limit')
            require(isinstance(wp.road_id, int) and isinstance(wp.lane_id, int), role + ' road/lane identity missing')
            points.append(xy)
            samples.append({'requested_xy': xy, 'native_waypoint_xy': native_xy, 'snap_m': snap,
                            'road_id': wp.road_id, 'lane_id': wp.lane_id, 'is_junction': bool(wp.is_junction)})
        routes[key] = points
        readbacks[role] = samples
    crossings = [segment_intersection(a, b, c, d)
                 for a, b in zip(routes['ego_route_xy'], routes['ego_route_xy'][1:])
                 for c, d in zip(routes['rider_route_xy'], routes['rider_route_xy'][1:])]
    require(any(point is not None for point in crossings), 'surveyed routes never intersect')
    require(any(sample['is_junction'] for samples in readbacks.values() for sample in samples), 'intersection waypoint readback missing')
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    # Seal the raw loaded map as a distinct source, then bind it from the route
    # packet. No hand-authored packet may stand in for the original map bytes.
    raw_path = out / 'native-map.xodr'
    raw_path.write_text(xodr, encoding='utf-8')
    raw_ref = {'path': raw_path.name, 'sha256': _sha(raw_path)}
    packet = {'assignment_id': ASSIGNMENT, 'cell_id': 'C111260',
              'native_map_name': name, 'native_opendrive': raw_ref,
              **routes, 'waypoint_readbacks': readbacks,
              'crossings_xy': [list(p) for p in crossings if p is not None],
              'max_waypoint_snap_m': snap_limit,
              'legal_verdict': None, 'physical_visibility_verdict': None}
    packet_ref = _write_json(out / 'native-route-survey.json', packet)
    return {'map_source_path': packet_ref['path'], 'original_sources': [raw_ref, packet_ref],
            'native_map_name': name, **routes, 'crossings_xy': packet['crossings_xy']}


def verify_packet(root, ref):
    """Check that a saved survey packet still binds the original map bytes."""
    base = Path(root).resolve()
    path = (base / ref['path']).resolve()
    require(path.is_relative_to(base) and path.is_file(), 'survey packet missing or escaping')
    require(_sha(path) == ref['sha256'], 'survey packet hash mismatch')
    packet = json.loads(path.read_text(encoding='utf-8'))
    raw = packet['native_opendrive']
    raw_path = (base / raw['path']).resolve()
    require(raw_path.is_relative_to(base) and raw_path.is_file(), 'original OpenDRIVE missing or escaping')
    require(_sha(raw_path) == raw['sha256'], 'original OpenDRIVE hash mismatch')
    require(packet['assignment_id'] == ASSIGNMENT and packet['cell_id'] == 'C111260', 'survey identity mismatch')
    require(packet['legal_verdict'] is None and packet['physical_visibility_verdict'] is None, 'unsupported survey verdict')
    return packet
