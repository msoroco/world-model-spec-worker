"""Source-gated 307(9)(b) straight-route construction and event audit.

The measured predicates are engineering observations. This module never makes a
legal permission, right-of-way, or malfunction finding from absence of motion.
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


def sealed(ref, root):
    base = Path(root).resolve()
    path = (base / ref['path']).resolve()
    require(path.is_relative_to(base) and path.is_file(), 'missing or escaping source')
    require(hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256'], 'source hash mismatch')
    return path


def verify_site(site, root):
    require(site['cell_id'] == 'C111125', 'wrong cell')
    require(site['actor'] == 'motorcycle_or_moped_operator', 'wrong actor')
    require(site['maneuver'] == 'straight' and site['control'] == 'traffic_light', 'fixed cell mismatch')
    refs = site['original_sources']
    for key in ('map_ref', 'route_ref', 'signal_ref', 'stop_ref', 'crosswalk_ref'):
        require(site[key] in refs, 'missing source binding: ' + key)
    for ref in refs.values():
        sealed(ref, root)
    require(site['ego_approach_id'] and site['official_head_id'], 'unbound governing head')
    require(site['facing_relation'] is True, 'head does not face approach')
    route = site['route_xy']
    require(len(route) >= 3, 'short route')
    for p in route:
        require(len(p) == 2 and all(math.isfinite(float(v)) for v in p), 'invalid point')
    dx, dy = route[-1][0]-route[0][0], route[-1][1]-route[0][1]
    require(dx*dx+dy*dy >= 100, 'short route')
    for x, y in route[1:-1]:
        require(abs((x-route[0][0])*dy-(y-route[0][1])*dx)/math.hypot(dx,dy) <= site['straight_tolerance_m'], 'route bends')
    require(site['stop_reference_kind'] in ('marked_stop_line', 'crosswalk_near_edge', 'intersection_near_edge'), 'invalid stopping reference')
    require(site['stop_reference_station_m'] < site['intersection_entry_station_m'], 'stop reference after entry')
    require(site['ego_blueprint_id'].startswith(('vehicle.', 'motorcycle.')), 'ego blueprint identity missing')
    require(site['ego_classification_source'], 'motorcycle classification source missing')
    return True


def construct_native(site, root, world, carla, blueprint_library):
    """Read Native map and official head before spawning; caller owns returned actor."""
    verify_site(site, root)
    require(world.get_map().name == site['native_map_name'], 'Native map readback mismatch')
    heads = {str(a.id): a for a in world.get_actors().filter('traffic.traffic_light*')}
    require(site['official_head_id'] in heads, 'governing head absent')
    bp = blueprint_library.find(site['ego_blueprint_id'])
    require(bp.id == site['ego_blueprint_id'], 'blueprint substitution')
    x, y = site['route_xy'][0]
    pose = carla.Transform(carla.Location(x=float(x), y=float(y), z=float(site['spawn_z_m'])), carla.Rotation(yaw=float(site['approach_yaw_deg'])))
    ego = world.try_spawn_actor(bp, pose)
    require(ego is not None, 'motorcycle spawn failed')
    try:
        require(ego.type_id == site['ego_blueprint_id'], 'spawned actor subtype mismatch')
        return {'ego': ego, 'head': heads[site['official_head_id']], 'route_xy': site['route_xy'], 'stop_reference_station_m': site['stop_reference_station_m']}
    except Exception:
        ego.destroy()
        raise


def measure_attempt(site, root, event_ref):
    """Read original frame history and count full aspect-return cycles after stop."""
    verify_site(site, root)
    rows = json.loads(sealed(event_ref, root).read_text())
    require(isinstance(rows, list) and len(rows) >= 4, 'frame history missing')
    prev_frame = -1
    prev_station = -math.inf
    stopped_frame = None
    entry_frame = None
    cycles = 0
    cycle_anchor = None
    last_composite = False
    departed = False
    cycle_bounds = []
    phase_history = []
    for row in rows:
        frame = row['frame']
        require(isinstance(frame, int) and frame > prev_frame, 'nonmonotonic frame')
        prev_frame = frame
        require(row['official_head_id'] == site['official_head_id'] and row['facing_approach_id'] == site['ego_approach_id'], 'unbound signal sample')
        require(row['actor_id'] and row['actor_type_id'] == site['ego_blueprint_id'], 'ego identity changed')
        aspects = row['lit_aspects']
        require(isinstance(aspects, list), 'signal aspects missing')
        require(row['speed_mps'] >= 0 and math.isfinite(row['speed_mps']), 'invalid speed')
        station = row['ego_front_station_m']
        require(math.isfinite(station) and station >= prev_station, 'invalid front trajectory')
        prev_station = station
        if row['speed_mps'] == 0 and station <= site['stop_reference_station_m'] and stopped_frame is None:
            stopped_frame = frame
        if station >= site['intersection_entry_station_m'] and entry_frame is None:
            entry_frame = frame
        composite = set(aspects) == {'steady_red', 'green_turn_arrow'} and len(aspects) == 2
        if stopped_frame is not None and frame >= stopped_frame and (entry_frame is None or frame < entry_frame):
            if composite and not last_composite:
                if cycle_anchor is not None and departed:
                    cycles += 1
                    cycle_bounds.append([cycle_anchor, frame])
                cycle_anchor = frame
                departed = False
            elif not composite and cycle_anchor is not None:
                departed = True
            last_composite = composite
        phase_history.append({'frame': frame, 'lit_aspects': aspects, 'ego_front_station_m': station})
    require(phase_history[0]['lit_aspects'] == ['steady_red', 'green_turn_arrow'], 'initial official composite phase absent')
    require(entry_frame is not None, 'ego never entered')
    require(stopped_frame is None or stopped_frame < entry_frame, 'stop occurred after entry')
    cause = site.get('unchanged_signal_cause')
    require(cause in ('malfunction', 'failed_detection', 'not_established'), 'invalid cause classification')
    if cause != 'not_established':
        require(site.get('cause_source_ref') in site['original_sources'], 'cause has no original source')
        packet = json.loads(sealed(site['original_sources'][site['cause_source_ref']], root).read_text())
        require(packet.get('official_head_id') == site['official_head_id'], 'cause head mismatch')
        require(packet.get('actor_type_id') == site['ego_blueprint_id'], 'cause actor mismatch')
        require(packet.get('classification') == cause, 'cause classification mismatch')
        require(packet.get('source_method') in ('native_signal_fault_readback', 'native_detector_readback', 'official_device_fault_record'), 'unsupported causal source method')
        require(packet.get('original_frame_start') is not None and packet.get('original_frame_end') is not None, 'causal interval missing')
        require(stopped_frame is None or packet['original_frame_start'] <= stopped_frame < packet['original_frame_end'], 'causal interval excludes stopped motorcycle')
    return {
        'stopped_frame': stopped_frame, 'entry_frame': entry_frame,
        'full_cycles_after_stop': cycles, 'cycle_frame_bounds_before_entry': cycle_bounds,
        'initial_composite_phase': True,
        'unchanged_signal_cause': cause, 'cause_source_ref': site.get('cause_source_ref'),
        'stop_reference_kind': site['stop_reference_kind'], 'stop_reference_station_m': site['stop_reference_station_m'],
        'frame_count': len(rows), 'phase_history': phase_history,
        'legal_permission_verdict': None, 'right_of_way_verdict': None,
        'original_sources': list(site['original_sources'].values()) + [event_ref],
    }


def control(site, observation):
    """Conservative straight controller requiring original observations."""
    require(observation['official_head_id'] == site['official_head_id'], 'wrong head')
    require(observation['facing_approach_id'] == site['ego_approach_id'], 'wrong approach')
    require(observation['frame'] >= 0, 'frame missing')
    require(observation['lit_aspects'] == ['steady_red', 'green_turn_arrow'], 'wrong governing phase')
    if observation['ego_front_station_m'] > site['stop_reference_station_m'] and not observation['stop_and_cycles_verified']:
        raise SourceError('stopping point already crossed')
    if not observation['stop_and_cycles_verified'] or observation['unchanged_signal_cause'] not in ('malfunction', 'failed_detection'):
        return {'throttle': 0.0, 'brake': 1.0, 'target': 'hold_before_stop_reference'}
    users = observation.get('other_users')
    require(isinstance(users, list), 'other-user original packet missing')
    if any(u.get('region') in ('adjacent_crosswalk', 'intersection') for u in users):
        return {'throttle': 0.0, 'brake': 1.0, 'target': 'yield_before_entry'}
    return {'throttle': site['proceed_throttle'], 'brake': 0.0, 'target': 'straight_route'}
