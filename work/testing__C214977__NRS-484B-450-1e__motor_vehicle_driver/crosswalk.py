"""Source-bound crosswalk parking construction and original-history observations."""
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

def sealed_json(ref, root):
    root = Path(root).resolve()
    path = (root / ref['path']).resolve()
    require(path.is_relative_to(root), 'source escapes root')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'source hash mismatch')
    return json.loads(raw)

def inside(point, polygon):
    x, y = point
    hit = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        x1, y1 = a
        x2, y2 = b
        if (y1 > y) != (y2 > y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1:
            hit = not hit
    return hit

def validate_site(site):
    require(site['cell_id'] == 'C214977' and site['layout'] == 'residence_district', 'wrong cell')
    require(site['map_name'] and site['highway_source'] and site['frontage_source'], 'road or residence source missing')
    require(site['crosswalk_source'] and site['marking_status_source'] and site['signal_governance_source'], 'crosswalk context missing')
    require(len(site['crosswalk_polygon']) >= 3 and len(site['parking_route']) >= 2, 'crosswalk or parking route missing')
    for p in site['crosswalk_polygon'] + site['parking_route']:
        require(len(p) == 2 and all(math.isfinite(float(v)) for v in p), 'invalid geometry')
    return site

def construct(adapter, site_ref, vehicle_ref, case, root):
    site = validate_site(sealed_json(site_ref, root))
    vehicle = sealed_json(vehicle_ref, root)
    require(vehicle['blueprint'] and vehicle['driver_source'], 'vehicle or driver source missing')
    require(case['action'] in {'stop', 'stand', 'park'}, 'unknown action')
    require(case['exception'] in {'none', 'traffic_conflict', 'law', 'police_direction', 'device_direction'}, 'unknown exception')
    readback = adapter.verify_crosswalk(site)
    require(readback['map_name'] == site['map_name'] and readback['crosswalk_polygon'] == site['crosswalk_polygon'], 'Native crosswalk readback mismatch')
    ego = adapter.spawn_vehicle(vehicle, site['parking_route'][0])
    require(ego['actor_id'] and ego['blueprint'] == vehicle['blueprint'], 'Native ego readback mismatch')
    adapter.configure_route(ego['actor_id'], site['parking_route'], case['destination'], case['action'])
    adapter.configure_exception(ego['actor_id'], case['exception'])
    return {'case_id': case['case_id'], 'subject_id': ego['actor_id'], 'map_name': site['map_name']}

def footprint_relation(corners, polygon):
    require(len(corners) == 4, 'body corners missing')
    count = sum(inside(p, polygon) for p in corners)
    # A crossing edge can overlap the crosswalk even when all corners lie outside.
    edges = list(zip(corners, corners[1:] + corners[:1]))
    def orient(a,b,c): return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def crosses(a,b,c,d):
        return orient(a,b,c)*orient(a,b,d) <= 0 and orient(c,d,a)*orient(c,d,b) <= 0
    edge_cross = any(crosses(a,b,c,d) for a,b in edges for c,d in zip(polygon, polygon[1:] + polygon[:1]))
    contained = count == 4
    overlap = bool(count or edge_cross or all(inside(p, corners) for p in polygon))
    return {'overlap': overlap, 'contained': contained, 'corners_inside': count}

def measure(rows, expected):
    require(len(rows) == expected['frame_count'] and len(rows) >= 2, 'frame count mismatch')
    active = []
    for i, row in enumerate(rows):
        require(row['frame'] == expected['first_frame'] + i, 'frame gap')
        require(row['case_id'] == expected['case_id'] and row['subject_id'] == expected['subject_id'], 'case or actor mismatch')
        require(math.isfinite(row['time_s']) and (i == 0 or abs(row['time_s']-rows[i-1]['time_s']-0.05) <= 0.001), 'not contiguous 20 Hz')
        require(math.isfinite(row['speed_mps']) and row['speed_mps'] >= 0, 'invalid speed')
        require(row['halt_activity'] in {'stop','stand','park','travel'}, 'activity missing')
        require(all(isinstance(row[k], bool) for k in ('traffic_conflict','law_direction','police_direction','device_direction')), 'exception source missing')
        require(row['crosswalk_id'] == expected['crosswalk_id'] and row['marking_status'] == expected['marking_status'], 'crosswalk context mismatch')
        relation = footprint_relation(row['body_corners_xy'], expected['crosswalk_polygon'])
        if row['halt_activity'] == expected['action'] and row['speed_mps'] < 0.1:
            active.append((i, relation, any(row[k] for k in ('traffic_conflict','law_direction','police_direction','device_direction'))))
    return {'case_id': expected['case_id'], 'frame_count': len(rows), 'halt_frames': len(active),
            'halt_overlapping_crosswalk_frames': sum(r['overlap'] for _,r,_ in active),
            'halt_contained_crosswalk_frames': sum(r['contained'] for _,r,_ in active),
            'halt_with_exception_source_frames': sum(e for _,_,e in active),
            'first_time_s': rows[0]['time_s'], 'last_time_s': rows[-1]['time_s'], 'legal_judgment': None}

def audit_saved(attempt, root):
    require(attempt['source_format'] == 'native_original' and attempt['fps'] == 20 and attempt['frame_count'] == 900, 'capture profile mismatch')
    require(set(attempt['cameras']) == {'front','rear','left','right'}, 'four-camera source missing')
    rows = sealed_json(attempt['actor_rows'], root)
    mapping = sealed_json(attempt['frame_map'], root)
    require(len(mapping) == 900, 'frame map incomplete')
    require(all(mapping[i]['frame'] == rows[i]['frame'] and mapping[i]['time_s'] == rows[i]['time_s'] for i in range(900)), 'frame map join mismatch')
    for ref in attempt['cameras'].values():
        require(ref['frame_count'] == 900 and ref['fps'] == 20, 'camera profile mismatch')
        path = (Path(root).resolve()/ref['path']).resolve()
        require(path.is_relative_to(Path(root).resolve()), 'camera escapes root')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256'], 'camera hash mismatch')
    return {'format':'crosswalk-original-source-audit', 'measurement':measure(rows, attempt['expected']),
            'full_video_decode':'pending_pinned_media_auditor', 'actual_pixels':'pending_physical_review'}

def audit_comparison(left, right, fixed_keys, changed_keys):
    require(left['case_id'] != right['case_id'], 'same case')
    require(all(left[k] == right[k] for k in fixed_keys), 'fixed condition changed')
    require(all(left[k] != right[k] for k in changed_keys), 'declared difference absent')
    return {'case_ids':[left['case_id'],right['case_id']], 'fixed_checked':list(fixed_keys), 'differences_checked':list(changed_keys)}
