"""CPU construction contract for a controlled entrance-device comparison.

The Native actor inventory establishes presence and trigger governance only.
Whether a device is official and how NRS 484B.250(2) applies need separate
original-source review. This module has no CARLA import or legal classifier.
"""
from contextlib import contextmanager
import math


DEVICE_PREFIXES = ('traffic.stop', 'traffic.traffic_light')


def entrance_devices(world, entrance_waypoint):
    """Read Native device actors whose triggers cover the exact entrance."""
    point = entrance_waypoint.transform.location
    devices = []
    for actor in world.get_actors():
        kind = actor.type_id
        if not kind.startswith(DEVICE_PREFIXES):
            continue
        if actor.trigger_volume.contains(point, actor.get_transform()):
            if type(actor.id) is not int or actor.id <= 0:
                raise ValueError('Native device actor ID required')
            devices.append({'native_id': actor.id, 'type_id': kind})
    ids = [row['native_id'] for row in devices]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate Native device actor identity')
    return sorted(devices, key=lambda row: (row['type_id'], row['native_id']))


def _xy(value, label):
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError('Finite ' + label + ' XY required')
    return value


def validate_device_pair(controlled, uncontrolled):
    """Require one measured contrast with crossing, paths and timing fixed."""
    common = ('native_map_id', 'intersection_id', 'same_statutory_crossing',
              'approach_relation', 'crossing_polygon_xy_m',
              'ego_road_lane', 'other_road_lane', 'ego_route_xy_m',
              'other_route_xy_m', 'other_release_frame', 'ego_hold_after_clear_frames')
    if any(controlled.get(key) != uncontrolled.get(key) for key in common):
        raise ValueError('Device comparison changed a fixed condition')
    if (controlled.get('source_scope') != 'synthetic_cpu_construction' or
            uncontrolled.get('source_scope') != 'synthetic_cpu_construction'):
        raise ValueError('Exact synthetic construction scope required')
    for row in (controlled, uncontrolled):
        if type(row.get('intersection_id')) is not int:
            raise ValueError('Exact intersection identity required')
        if (row.get('same_statutory_crossing') is not True or
                row.get('approach_relation') != 'different_highways'):
            raise ValueError('Different-highway statutory crossing required')
        if not isinstance(row.get('native_map_id'), str) or not row['native_map_id']:
            raise ValueError('Native map identity required')
        for key in ('crossing_polygon_xy_m', 'ego_route_xy_m', 'other_route_xy_m'):
            if not isinstance(row.get(key), list) or len(row[key]) < 3:
                raise ValueError('Complete ' + key + ' required')
            for point in row[key]:
                _xy(point, key)
        if type(row.get('other_release_frame')) is not int or type(row.get('ego_hold_after_clear_frames')) is not int:
            raise ValueError('Exact controller setpoints required')
        if row.get('official_device_judgment') != 'unresolved':
            raise ValueError('Official status requires independent source review')
    if (controlled.get('expected_entrance_device') != 'present' or
            uncontrolled.get('expected_entrance_device') != 'absent'):
        raise ValueError('Present and absent device constructions required')
    return {'comparison_kind': 'entrance_device_presence',
            'fixed_conditions': list(common),
            'measured_presence_values': ['present', 'absent'],
            'official_device_judgment': 'unresolved',
            'legal_acceptance_claimed': False,
            'physical_acceptance_claimed': False}


def check_entrance_device_expectation(observed, expected):
    """Reject a Native entrance that does not realize the construction."""
    if expected not in ('present', 'absent'):
        raise ValueError('Exact device-presence expectation required')
    if (expected == 'present') != bool(observed):
        raise ValueError('Native entrance device presence differs from construction')
    return {'observed_native_device_ids': [row['native_id'] for row in observed],
            'presence': expected,
            'official_device_judgment': 'unresolved'}


def build_presence_pair(scene, release_frame=40, hold_frames=0):
    """Make two exact CPU scene contracts with one changed device dimension."""
    ego, other = scene['approaches']['ego'], scene['approaches']['other']
    common = {'native_map_id': scene['native_map_name'],
              'intersection_id': scene['intersection_id'],
              'same_statutory_crossing': scene['same_statutory_crossing'],
              'approach_relation': scene['approach_relation'],
              'crossing_polygon_xy_m': scene['crossing_polygon_xy_m'],
              'ego_road_lane': [ego['road_id'], ego['lane_id']],
              'other_road_lane': [other['road_id'], other['lane_id']],
              'ego_route_xy_m': ego['route_xy_m'],
              'other_route_xy_m': other['route_xy_m'],
              'other_release_frame': release_frame,
              'ego_hold_after_clear_frames': hold_frames,
              'source_scope': 'synthetic_cpu_construction',
              'official_device_judgment': 'unresolved'}
    present = {**common, 'expected_entrance_device': 'present'}
    absent = {**common, 'expected_entrance_device': 'absent'}
    validate_device_pair(present, absent)
    return present, absent


@contextmanager
def construct_device_pair(world, entrance_waypoint, setup, ego_blueprint,
                          other_blueprint, ego_transform, other_transform):
    """Spawn an owned pair only when Native device presence matches the setup."""
    devices = entrance_devices(world, entrance_waypoint)
    check_entrance_device_expectation(devices, setup['expected_entrance_device'])
    owned = []
    try:
        for role, blueprint, transform in (
                ('ego', ego_blueprint, ego_transform),
                ('other', other_blueprint, other_transform)):
            actor = world.try_spawn_actor(blueprint, transform)
            if actor is None:
                raise ValueError(role + ' Native spawn failed')
            owned.append(actor)
        yield owned[0], owned[1], devices
    finally:
        for actor in reversed(owned):
            actor.destroy()
