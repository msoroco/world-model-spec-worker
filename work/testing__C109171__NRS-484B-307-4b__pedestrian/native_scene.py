"""Source-gated pedestrian entry construction for NRS 484B.307(4)(b).

The operator supplies original Native map and signal bindings; this module never
creates an official signal, signal phase, or legal permission from a label.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


class SourceError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise SourceError(message)


def _source(ref, root):
    path = Path(root, ref['path']).resolve()
    _require(path.is_relative_to(Path(root).resolve()), 'source escapes attempt root')
    _require(path.is_file(), 'missing original source: '+ref['path'])
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    _require(digest == ref['sha256'], 'source hash mismatch: '+ref['path'])
    return path


def verify_site(site, root):
    """Check source-backed intersection layout before any actor is spawned."""
    _require(site['cell_id'] == 'C109171', 'cell mismatch')
    _require(site['actor'] == 'pedestrian', 'actor mismatch')
    refs = site['original_sources']
    _require(len(refs) >= 3, 'map, vehicle signal and pedestrian signal sources required')
    for ref in refs:
        _source(ref, root)
    _require(site['map_source_path'] in [r['path'] for r in refs], 'map source unbound')
    _require(site['vehicle_signal_source_path'] in [r['path'] for r in refs], 'vehicle signal source unbound')
    _require(site['pedestrian_device_source_path'] in [r['path'] for r in refs], 'pedestrian signal source unbound')
    _require(site['official_vehicle_head_id'] != site['pedestrian_device_id'], 'permission must be a separate device')
    _require(site['pedestrian_device_governs_route'] is True, 'pedestrian device route relation unverified')
    def packet(path):
        ref = next(r for r in refs if r['path'] == path)
        value = json.loads(_source(ref, root).read_text())
        _require(isinstance(value, dict), 'original site packet must be an object')
        return value
    map_packet = packet(site['map_source_path'])
    head_packet = packet(site['vehicle_signal_source_path'])
    device_packet = packet(site['pedestrian_device_source_path'])
    _require(map_packet.get('highway_boundary_xy') == site['highway_boundary_xy'], 'highway boundary differs from original map')
    _require(map_packet.get('pedestrian_route_xy') == site['pedestrian_route_xy'], 'pedestrian route differs from original map')
    _require(map_packet.get('route_id') == site['pedestrian_route_id'], 'pedestrian route identity differs from original map')
    _require(head_packet.get('head_id') == site['official_vehicle_head_id'] and head_packet.get('official') is True,
             'official vehicle signal head differs from original source')
    _require(head_packet.get('sole_green_arrow_aspect') == site['sole_green_arrow_aspect'], 'arrow aspect differs from original source')
    _require(device_packet.get('device_id') == site['pedestrian_device_id'] and
             device_packet.get('governs_route_id') == site['pedestrian_route_id'],
             'pedestrian permission device differs from original source')
    route = site['pedestrian_route_xy']
    boundary = site['highway_boundary_xy']
    _require(len(route) >= 3 and len(boundary) >= 3, 'route and highway polygon required')
    for pt in route+boundary:
        _require(len(pt) == 2 and all(math.isfinite(float(v)) for v in pt), 'nonfinite point')
    _require(not inside_highway(route[0], boundary), 'route must begin outside highway')
    _require(any(inside_highway(pt, boundary) for pt in route[1:]), 'route never enters highway')
    _require(site['pedestrian_faces_vehicle_head'] is True, 'facing relationship unverified')
    return True


def inside_highway(point, polygon):
    """Ray casting for a surveyed highway surface polygon, boundary included."""
    x, y = map(float, point)
    n = len(polygon)
    for i in range(n):
        x1, y1 = map(float, polygon[i])
        x2, y2 = map(float, polygon[(i+1) % n])
        cross = (x-x1)*(y2-y1)-(y-y1)*(x2-x1)
        if abs(cross) <= 1e-8 and min(x1,x2)-1e-8 <= x <= max(x1,x2)+1e-8 and min(y1,y2)-1e-8 <= y <= max(y1,y2)+1e-8:
            return True
    result = False
    for i in range(n):
        x1,y1 = map(float, polygon[i]); x2,y2 = map(float, polygon[(i+1)%n])
        if (y1 > y) != (y2 > y) and x < x1 + (y-y1)*(x2-x1)/(y2-y1):
            result = not result
    return result


def measure_attempt(site, root, events_ref):
    """Read original frame events and report facts, never a legal verdict."""
    verify_site(site, root)
    events = json.loads(_source(events_ref, root).read_text())
    _require(isinstance(events, list) and len(events) > 1, 'at least two frame events required')
    previous = -1
    entry = None
    records = []
    for row in events:
        frame = row['frame']
        _require(isinstance(frame, int) and frame == previous+1, 'frame sequence invalid')
        previous = frame
        _require(row['vehicle_head_id'] == site['official_vehicle_head_id'], 'vehicle signal identity mismatch')
        _require(row['pedestrian_device_id'] == site['pedestrian_device_id'], 'pedestrian device identity mismatch')
        lit = row['vehicle_head_lit_aspects']
        _require(isinstance(lit, list), 'original lit aspects required')
        sole_arrow = len(lit) == 1 and lit[0] == site['sole_green_arrow_aspect']
        _require(sole_arrow, 'vehicle head is not sole green turn arrow')
        _require(row['pedestrian_facing_vehicle_head'] is True, 'facing not evidenced at frame')
        inside = inside_highway(row['pedestrian_xy'], site['highway_boundary_xy'])
        if not records:
            _require(not inside, 'first captured frame is already in highway')
        permission = row['pedestrian_device_indication'] == 'WALK'
        records.append({'frame':frame,'inside_highway':inside,'separate_walk_indication':permission})
        if inside and entry is None:
            _require(len(records) > 1 and not records[-2]['inside_highway'], 'entry has no outside bracket')
            entry = {'frame':frame,'previous_outside_frame':records[-2]['frame'],
                     'sampled_entry_bracket_frames':[records[-2]['frame'],frame],
                     'separate_walk_indication':permission,'pedestrian_xy':row['pedestrian_xy']}
    _require(not records[0]['inside_highway'], 'first captured frame is already in highway')
    return {'first_highway_entry':entry,'frames':len(records),'sole_green_arrow_frames':len(records),'records':records,'original_sources':[events_ref]+site['original_sources']}
