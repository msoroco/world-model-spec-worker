"""Original-source crossing measurements for NRS 484B.307(2)(b).

Site geometry and device identity are supplied by the Native operator. This
module measures facts and deliberately makes no legal permission decision.
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
    require(path.is_relative_to(base) and path.is_file(), 'missing or escaping original source')
    require(hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256'], 'original source hash mismatch')
    return path


def inside(point, polygon):
    x, y = map(float, point)
    require(len(polygon) >= 3, 'polygon has fewer than three vertices')
    hit = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        ax, ay = map(float, a)
        bx, by = map(float, b)
        require(all(map(math.isfinite, (ax, ay, bx, by, x, y))), 'nonfinite geometry')
        cross = (x-ax)*(by-ay) - (y-ay)*(bx-ax)
        if abs(cross) < 1e-8 and min(ax,bx)-1e-8 <= x <= max(ax,bx)+1e-8 and min(ay,by)-1e-8 <= y <= max(ay,by)+1e-8:
            return True
        if (ay > y) != (by > y) and x < ax + (y-ay)*(bx-ax)/(by-ay):
            hit = not hit
    return hit


def verify_site(site, root):
    require(site['cell_id'] == 'C111125' and site['actor'] == 'pedestrian', 'wrong assignment site')
    refs = site['original_sources']
    require(len(refs) >= 3, 'map, signal and device inventory sources required')
    for ref in refs:
        source(ref, root)
    paths = {r['path'] for r in refs}
    for key in ('map_source_path', 'signal_source_path', 'device_inventory_source_path'):
        require(site[key] in paths, 'unbound site source: ' + key)
    map_data = json.loads(source(next(r for r in refs if r['path'] == site['map_source_path']), root).read_text())
    signal_data = json.loads(source(next(r for r in refs if r['path'] == site['signal_source_path']), root).read_text())
    device_data = json.loads(source(next(r for r in refs if r['path'] == site['device_inventory_source_path']), root).read_text())
    require(map_data.get('public_highway') is True and site['public_highway_source_assertion'] is True,
            'public highway status unverified')
    for key in ('highway_polygon_xy', 'crosswalk_polygon_xy', 'crosswalk_kind'):
        require(map_data.get(key) == site.get(key), 'map geometry or crosswalk kind differs: ' + key)
    require(map_data.get('crosswalk_qualifies') is True and site['crosswalk_qualification_source_assertion'] is True,
            'crosswalk qualification unverified')
    require(signal_data.get('official') is True and signal_data.get('control') == 'traffic_light',
            'official traffic light source unavailable')
    require(signal_data.get('head_id') == site['official_signal_head_id'], 'signal head source mismatch')
    require(signal_data.get('pedestrian_faces_head') is True, 'source facing relationship unverified')
    require(device_data.get('other_device_id') == site['other_device_id'], 'device inventory mismatch')
    require(device_data.get('inventory_complete') is True, 'other device inventory incomplete')
    require(site['official_signal_head_id'] and site['pedestrian_faces_head'] is True, 'official facing head unverified')
    require(site['crosswalk_kind'] in ('marked', 'unmarked'), 'unknown crosswalk kind')
    route = site['pedestrian_route_xy']
    require(len(route) >= 3, 'route needs sidewalk, crossing and far side')
    require(not inside(route[0], site['highway_polygon_xy']), 'route starts inside highway')
    if site.get('route_crosswalk_expected', True):
        require(any(inside(pt, site['crosswalk_polygon_xy']) for pt in route[1:]), 'route never enters crosswalk')
    else:
        require(all(not inside(pt, site['crosswalk_polygon_xy']) for pt in route), 'outside route enters crosswalk')
    require(any(inside(pt, site['highway_polygon_xy']) for pt in route[1:]), 'route never enters highway')
    return True


def spawn_pedestrian(world, site, root, blueprint_library, transform_factory):
    """Spawn only after the original map/device bindings and route are checked."""
    verify_site(site, root)
    blueprint_id = site['pedestrian_blueprint_id']
    require(blueprint_id.startswith('walker.pedestrian.'), 'pedestrian blueprint required')
    blueprint = blueprint_library.find(blueprint_id)
    transform = transform_factory(*site['pedestrian_spawn_xyz'])
    actor = world.try_spawn_actor(blueprint, transform)
    require(actor is not None, 'pedestrian spawn failed')
    try:
        actual = actor.get_transform()
        require(actual is not None, 'spawn transform readback unavailable')
        require(actor.type_id == blueprint_id, 'spawn blueprint readback mismatch')
        return actor
    except Exception:
        actor.destroy()
        raise


def measure(site, root, events_ref):
    verify_site(site, root)
    rows = json.loads(source(events_ref, root).read_text())
    require(isinstance(rows, list) and len(rows) > 1, 'original frame history required')
    previous = -1
    first_entry = None
    measurements = []
    for row in rows:
        frame = row['frame']
        require(isinstance(frame, int) and frame > previous, 'frames must increase')
        previous = frame
        require(row['official_signal_head_id'] == site['official_signal_head_id'], 'signal head changed')
        require(row['pedestrian_faces_head'] is True, 'facing relationship not observed')
        require(isinstance(row['lit_aspects'], list), 'lit aspects absent')
        green_alone = row['lit_aspects'] == ['circular_green']
        in_highway = inside(row['pedestrian_xy'], site['highway_polygon_xy'])
        in_crosswalk = inside(row['pedestrian_xy'], site['crosswalk_polygon_xy'])
        device = row['other_device_indication']
        require(device in ('none', 'WALK', 'DONT_WALK', 'WAIT', 'unknown'), 'device state missing')
        require(row['other_device_id'] == site['other_device_id'], 'other-device identity changed')
        mode = row.get('other_device_mode', 'unknown')
        require(mode in ('absent', 'walk', 'flashing_countdown', 'flashing_no_countdown',
                         'steady', 'unknown'), 'other-device display mode invalid')
        countdown = row.get('other_device_countdown')
        require(countdown is None or (isinstance(countdown, int) and countdown >= 0),
                'other-device countdown invalid')
        if mode == 'flashing_countdown':
            require(countdown is not None, 'flashing countdown lacks observed value')
        fact = {'frame': frame, 'green_alone': green_alone, 'in_highway': in_highway,
                'in_crosswalk': in_crosswalk, 'other_device_indication': device,
                'other_device_mode': mode, 'other_device_countdown': countdown}
        measurements.append(fact)
        if in_highway and first_entry is None:
            first_entry = fact
    require(not measurements[0]['in_highway'], 'capture starts after highway entry')
    entry_index = next((i for i, fact in enumerate(measurements) if fact['in_highway']), None)
    entry_transition = None
    if entry_index is not None:
        entry = measurements[entry_index]
        before = measurements[entry_index - 1]
        entry_transition = {
            'before_frame': before['frame'],
            'entry_frame': entry['frame'],
            'before_device_mode': before['other_device_mode'],
            'entry_device_mode': entry['other_device_mode'],
            'before_device_indication': before['other_device_indication'],
            'entry_device_indication': entry['other_device_indication'],
            'before_green_alone': before['green_alone'],
            'entry_green_alone': entry['green_alone'],
            'entered_within_crosswalk': entry['in_crosswalk'],
        }
    return {'first_highway_entry': first_entry, 'entry_transition': entry_transition,
            'measurements': measurements,
            'crosswalk_kind': site['crosswalk_kind'], 'frame_count': len(rows),
            'original_sources': refs_with_events(site['original_sources'], events_ref),
            'legal_verdict': None, 'physical_acceptance': False}


def refs_with_events(refs, events_ref):
    return [events_ref, *refs]
