"""Reviewed site packet and Native spawn contract for NRS 484B.257(2).

The packet must be supplied from original map/device review. This module does
not infer a through-highway classification or a participant's obligation from
the authored cell name.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _number(value, name):
    _require(type(value) in (int, float) and math.isfinite(value), 'invalid ' + name)
    return float(value)


def _point(value, name):
    _require(isinstance(value, list) and len(value) == 3, 'missing xyz ' + name)
    return tuple(_number(v, name) for v in value)


def _source(record, name, base):
    _require(isinstance(record, dict), 'missing reviewed source ' + name)
    path = record.get('path')
    digest = record.get('sha256')
    _require(isinstance(path, str) and path and isinstance(digest, str) and
             len(digest) == 64 and all(c in '0123456789abcdef' for c in digest),
             'missing source path/hash ' + name)
    source = Path(path)
    if not source.is_absolute():
        source = base / source
    _require(source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest() == digest,
             'reviewed source absent or changed ' + name)


def validate_site(packet_path, expected_case=None):
    """Require a sourced real intersection and a uniquely governed approach."""
    path = Path(packet_path)
    _require(path.is_file(), 'reviewed yield site packet missing')
    packet = json.loads(path.read_text())
    _require(packet.get('format') == 'c158208-reviewed-native-site-v1',
             'wrong yield site packet format')
    _require(packet.get('cell_id') == 'C158208' and
             packet.get('law_id') == 'NRS-484B-257-2' and
             packet.get('actor') == 'motor_vehicle_driver', 'wrong exact site identity')
    if expected_case is not None:
        _require(packet.get('case_id') == expected_case, 'wrong selected site case')
    for name in ('map_opendrive', 'jurisdiction', 'intersection_geometry',
                 'non_through_classification',
                 'all_entrance_controls', 'ego_yield_sign', 'stop_reference',
                 'ego_route', 'ego_vehicle', 'other_route', 'other_obligation',
                 'through_vehicle_exemption', 'sightlines',
                 'officer_control', 'signal_control'):
        _source(packet.get('sources', {}).get(name), name, path.parent)
    _require(packet.get('non_through_highway') is True and
             packet.get('ego_yield_sign_present') is True and
             packet.get('other_obligated_to_stop_or_yield') is False and
             packet.get('officer_controls') is False and
             packet.get('signal_controls') is False,
             'statutory scene context not established by reviewed packet')
    entrances = packet.get('entrances')
    _require(isinstance(entrances, list) and len(entrances) >= 2 and
             len({row.get('id') for row in entrances if isinstance(row, dict)}) == len(entrances),
             'all entrance controls are required')
    _require(all(isinstance(row, dict) and row.get('id') and
                 row.get('control') in ('stop', 'yield', 'none') and
                 row.get('reviewed_source') for row in entrances),
             'entrance control inventory incomplete')
    ego_entrance = packet.get('ego_entrance_id')
    other_entrance = packet.get('other_entrance_id')
    _require(ego_entrance != other_entrance and
             next((row['control'] for row in entrances if row['id'] == ego_entrance), None) == 'yield' and
             next((row['control'] for row in entrances if row['id'] == other_entrance), None) == 'none',
             'ego/other entrance obligation mismatch')
    stop = _number(packet.get('stop_reference_station_m'), 'stop reference')
    entry = _number(packet.get('intersection_entry_station_m'), 'intersection entry')
    _require(stop < entry, 'stop reference must precede physical entry')
    spawn = packet.get('spawn_plan')
    _require(isinstance(spawn, dict) and set(spawn) == {'ego', 'other'},
             'reviewed spawn plan requires ego and other vehicle')
    for name in ('ego', 'other'):
        spec = spawn[name]
        _require(isinstance(spec, dict) and spec.get('blueprint_id') and
                 spec.get('source_citation') and spec.get('route_source_citation'),
                 'uncited ' + name + ' spawn/route')
        _point(spec.get('location_xyz_m'), name + ' spawn')
        _point(spec.get('rotation_rpy_deg'), name + ' rotation')
        route = spec.get('route_points_xyz_m')
        _require(isinstance(route, list) and len(route) >= 2,
                 name + ' connected route absent')
        for p in route:
            _point(p, name + ' route')
    _require(_number(spawn['ego'].get('initial_station_m'), 'ego initial station') < stop,
             'ego spawn not upstream of yield reference')
    _require(packet.get('intersection_polygon_source') and
             packet.get('ego_route_continuity_review') is True and
             packet.get('other_route_continuity_review') is True,
             'physical intersection or route review missing')
    return packet


class NativeActors:
    def __init__(self, ego, other, owned):
        self.ego = ego
        self.other = other
        self.owned = owned

    def close(self):
        for actor in reversed(self.owned):
            actor.destroy()
        self.owned.clear()


def create(world, packet_path, transform_factory, expected_case=None):
    """Spawn only owned actors and release them on any partial failure."""
    packet = validate_site(packet_path, expected_case)
    owned = []
    try:
        library = world.get_blueprint_library()
        actors = {}
        for name in ('ego', 'other'):
            spec = packet['spawn_plan'][name]
            blueprint = library.find(spec['blueprint_id'])
            transform = transform_factory(tuple(spec['location_xyz_m']),
                                          tuple(spec['rotation_rpy_deg']))
            actor = world.try_spawn_actor(blueprint, transform)
            _require(actor is not None, 'Native ' + name + ' spawn failed')
            owned.append(actor)
            actors[name] = actor
        return NativeActors(actors['ego'], actors['other'], owned)
    except Exception:
        for actor in reversed(owned):
            actor.destroy()
        raise
