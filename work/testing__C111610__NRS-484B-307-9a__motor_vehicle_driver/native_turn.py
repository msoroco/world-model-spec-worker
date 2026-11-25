"""Source-bound Native plan and measurement for the red-plus-green-arrow turn.

This module consumes original map/signal/actor records. It does not assert that
a CARLA light is an official device or that a pedestrian is lawfully present.
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


def read_source(root, ref):
    base = Path(root).resolve()
    path = (base / ref['path']).resolve()
    require(path.is_relative_to(base), 'source escapes attempt root')
    require(path.is_file(), 'missing original source: ' + ref['path'])
    require(hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256'],
            'source hash mismatch: ' + ref['path'])
    return json.loads(path.read_text())


def point_in_polygon(point, polygon):
    x, y = map(float, point)
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        ax, ay = map(float, a)
        bx, by = map(float, b)
        cross = (x - ax) * (by - ay) - (y - ay) * (bx - ax)
        if abs(cross) < 1e-8 and min(ax, bx) - 1e-8 <= x <= max(ax, bx) + 1e-8 and min(ay, by) - 1e-8 <= y <= max(ay, by) + 1e-8:
            return True
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            inside = not inside
    return inside


def verify_site(site, root):
    require(site['cell_id'] == 'C111610' and site['actor'] == 'motor_vehicle_driver', 'fixed cell or actor mismatch')
    refs = site['original_sources']
    require(set(refs) == {'map', 'ego_signal', 'opposing_signal', 'crosswalk', 'pedestrian_permission', 'other_traffic'}, 'missing site sources')
    records = {key: read_source(root, ref) for key, ref in refs.items()}
    map_data = records['map']
    require(map_data['intersection_id'] == site['intersection_id'], 'intersection identity mismatch')
    require(site['ego_approach_lane_id'] in map_data['lane_ids'], 'ego lane not in map')
    require(site['arrow_destination_lane_id'] in map_data['lane_ids'], 'arrow destination not in map')
    require(site['straight_destination_lane_id'] in map_data['lane_ids'], 'straight destination not in map')
    require(site['arrow_destination_lane_id'] != site['straight_destination_lane_id'], 'different movements must use different lanes')
    require(records['ego_signal']['head_id'] == site['ego_head_id'], 'ego signal identity mismatch')
    require(records['opposing_signal']['head_id'] == site['opposing_head_id'], 'opposing signal identity mismatch')
    require(records['ego_signal']['governed_lane_ids'] == [site['ego_approach_lane_id']], 'ego head does not govern approach')
    require(records['crosswalk']['crosswalk_id'] == site['adjacent_crosswalk_id'], 'crosswalk identity mismatch')
    require(records['crosswalk']['adjacent_to_turn'] is True, 'crosswalk adjacency unverified')
    polygon = records['crosswalk']['polygon_xy']
    require(len(polygon) >= 3 and all(len(p) == 2 and all(math.isfinite(float(v)) for v in p) for p in polygon), 'invalid crosswalk polygon')
    require(records['pedestrian_permission']['crosswalk_id'] == site['adjacent_crosswalk_id'], 'pedestrian permission not tied to crosswalk')
    require(records['pedestrian_permission']['lawfulness_basis'] in ('walk_device', 'lawful_entry_context'), 'pedestrian lawfulness source missing')
    require(records['other_traffic']['actor_id'] == site['other_traffic_actor_id'], 'other traffic identity mismatch')
    require(records['other_traffic']['intersection_id'] == site['intersection_id'], 'other traffic intersection mismatch')
    require(records['other_traffic']['route_lane_id'] in map_data['lane_ids'], 'other traffic lane not in map')
    return records


def case_command(case_suffix, observed_pedestrian_in_crosswalk):
    """Native route/controller intent; the recorder must verify actual motion."""
    commands = {
        'yield_pedestrian': ('arrow_turn', 'hold_until_clear'),
        'continue_pedestrian': ('arrow_turn', 'continue'),
        'clear_crosswalk_turn': ('arrow_turn', 'hold_until_clear'),
        'wrong_movement': ('straight', 'hold_until_clear'),
        'yield_other_traffic': ('arrow_turn', 'hold_until_clear'),
        'continue_other_traffic': ('arrow_turn', 'continue'),
    }
    require(case_suffix in commands, 'unknown exact case')
    route, policy = commands[case_suffix]
    require(observed_pedestrian_in_crosswalk is True or case_suffix in ('clear_crosswalk_turn', 'wrong_movement', 'yield_other_traffic', 'continue_other_traffic'), 'required pedestrian not observed')
    return {'route': route, 'controller_policy': policy, 'record_actual_route': True,
            'record_original_signal_heads': True, 'record_original_actor_boxes': True}


def construct_native(site, root, world, blueprint_library, carla, case_suffix, spawn_plan):
    """Spawn real actors only after source and transform bindings are verified.

    ``world`` and ``carla`` are injected so CPU tests can exercise the calls.
    The official signal heads are observed from the map, never spawned here.
    """
    verify_site(site, root)
    command = case_command(case_suffix, case_suffix in ('yield_pedestrian', 'continue_pedestrian'))
    require(set(spawn_plan) == {'ego', 'pedestrian', 'other_traffic'}, 'spawn plan roles missing')
    require(spawn_plan['pedestrian']['actor_id'] == site['pedestrian_actor_id'], 'pedestrian spawn identity unbound')
    require(spawn_plan['other_traffic']['actor_id'] == site['other_traffic_actor_id'], 'other traffic spawn identity unbound')
    spawned = {}
    try:
        for role in ('ego', 'pedestrian', 'other_traffic'):
            spec = spawn_plan[role]
            require(spec['source_ref'] in site['spawn_sources'], 'spawn source not bound: ' + role)
            source = read_source(root, site['spawn_sources'][spec['source_ref']])
            require(source.get('spawn_role') == role, 'spawn role source mismatch: ' + role)
            require(source.get('blueprint_id') == spec['blueprint_id'], 'blueprint source mismatch: ' + role)
            xyz = source.get('spawn_xyz')
            yaw = source.get('spawn_yaw')
            require(len(xyz) == 3 and all(math.isfinite(float(v)) for v in xyz) and math.isfinite(float(yaw)), 'spawn transform invalid: ' + role)
            blueprint = blueprint_library.find(spec['blueprint_id'])
            require(blueprint is not None, 'blueprint unavailable: ' + role)
            transform = carla.Transform(carla.Location(*map(float, xyz)), carla.Rotation(yaw=float(yaw)))
            actor = world.try_spawn_actor(blueprint, transform)
            require(actor is not None, 'Native actor spawn failed: ' + role)
            spawned[role] = actor
        return {'actors': spawned, 'command': command}
    except Exception:
        for actor in spawned.values():
            actor.destroy()
        raise


def controller_step(command, pedestrian_in_crosswalk, other_traffic_in_intersection):
    """Emit a Native control intent from current measured occupancy."""
    occupied = bool(pedestrian_in_crosswalk or other_traffic_in_intersection)
    if command['controller_policy'] == 'hold_until_clear' and occupied:
        return {'throttle': 0.0, 'brake': 1.0, 'route': command['route']}
    return {'throttle': 0.25, 'brake': 0.0, 'route': command['route']}


def audit_case_measurement(case_suffix, measured):
    """Check realized distinction using original frames, without a legal verdict."""
    require(case_suffix in ('yield_pedestrian', 'continue_pedestrian', 'clear_crosswalk_turn',
                            'wrong_movement', 'yield_other_traffic', 'continue_other_traffic'), 'unknown exact case')
    rows = measured['measurements']
    entry = measured['first_ego_entry']
    require(rows and entry in rows, 'original ego entry frame missing')
    route = entry['ego_route_lane_id']
    if case_suffix == 'wrong_movement':
        require(route != measured['arrow_destination_lane_id'], 'straight movement distinction not observed')
    else:
        require(route == measured['arrow_destination_lane_id'], 'arrow movement not observed')
    approach = [r for r in rows if r['frame'] <= entry['frame']]
    if case_suffix in ('yield_pedestrian', 'continue_pedestrian'):
        require(any(r['pedestrian_inside_adjacent_crosswalk'] and r['pedestrian_lawful_context'] for r in approach), 'lawful pedestrian not observed')
        occupied_at_entry = entry['pedestrian_inside_adjacent_crosswalk'] and entry['pedestrian_lawful_context']
        require(occupied_at_entry == (case_suffix == 'continue_pedestrian'), 'pedestrian precedence difference not observed')
    elif case_suffix in ('yield_other_traffic', 'continue_other_traffic'):
        require(any(r['other_traffic_lawfully_in_intersection'] for r in approach), 'lawful other traffic not observed')
        require(entry['other_traffic_lawfully_in_intersection'] == (case_suffix == 'continue_other_traffic'), 'other traffic precedence difference not observed')
    else:
        require(not any(r['pedestrian_inside_adjacent_crosswalk'] and r['pedestrian_lawful_context'] for r in approach), 'crosswalk not clear')
    return {'case_suffix': case_suffix, 'first_entry_frame': entry['frame'],
            'original_frames_checked': len(rows), 'legal_verdict': None,
            'physical_acceptance': False}


def measure_attempt(site, root, frames_ref):
    records = verify_site(site, root)
    frames = read_source(root, frames_ref)
    require(isinstance(frames, list) and len(frames) >= 2, 'original frame history required')
    crosswalk = records['crosswalk']['polygon_xy']
    last_frame = -1
    measurements = []
    for row in frames:
        frame = row['frame']
        require(isinstance(frame, int) and frame == last_frame + 1, 'frame history gap')
        last_frame = frame
        require(row['ego_head_id'] == site['ego_head_id'] and row['opposing_head_id'] == site['opposing_head_id'], 'signal head binding mismatch')
        require(row['ego_red'] is True and row['ego_arrow_direction'] == site['arrow_direction'], 'red plus arrow not observed')
        require(row['opposing_red'] is True, 'opposing steady red not observed')
        require(row['pedestrian_actor_id'] == site['pedestrian_actor_id'], 'pedestrian identity mismatch')
        require(row['pedestrian_permission_source_id'] == records['pedestrian_permission']['source_id'], 'pedestrian permission source mismatch')
        require(row['other_traffic_actor_id'] == site['other_traffic_actor_id'], 'other traffic actor mismatch')
        require(isinstance(row['other_traffic_lawful_context'], bool), 'other traffic lawfulness context missing')
        require(isinstance(row['other_traffic_in_intersection'], bool), 'other traffic occupancy missing')
        require(isinstance(row['pedestrian_lawful_context'], bool), 'pedestrian lawful context missing')
        require(row['ego_route_lane_id'] in records['map']['lane_ids'], 'actual ego lane unknown')
        require(isinstance(row['ego_in_intersection'], bool), 'entry measurement missing')
        pedestrian_inside = point_in_polygon(row['pedestrian_xy'], crosswalk)
        measurements.append({'frame': frame, 'pedestrian_inside_adjacent_crosswalk': pedestrian_inside,
                             'pedestrian_lawful_context': row['pedestrian_lawful_context'],
                             'ego_in_intersection': row['ego_in_intersection'],
                             'ego_route_lane_id': row['ego_route_lane_id'],
                             'other_traffic_lawfully_in_intersection': row['other_traffic_lawful_context'] and row['other_traffic_in_intersection'],
                             'ego_speed_mps': float(row['ego_speed_mps'])})
    first_entry = next((r for r in measurements if r['ego_in_intersection']), None)
    require(first_entry is not None, 'ego intersection entry not captured')
    require(all(math.isfinite(r['ego_speed_mps']) and r['ego_speed_mps'] >= 0 for r in measurements), 'invalid original speed')
    return {'first_ego_entry': first_entry, 'measurements': measurements,
            'arrow_destination_lane_id': site['arrow_destination_lane_id'],
            'source_refs': [frames_ref] + list(site['original_sources'].values()),
            'legal_verdict': None, 'physical_acceptance': False}
