"""Source-gated construction and original-history measurement for C111304.

A site adapter supplies map topology and spawn primitives. No CARLA import occurs
until an operator supplies that adapter. Engineering gaps are never legal cutoffs.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    case_id: str
    subject: str  # person_occupant or property
    public_access_basis: str  # highway or public_access_premises
    approach: str  # northbound or southbound
    ego_speed_mps: float
    crossing_speed_mps: float
    crossing_release_s: float


CASES = (
    Case('person_north_early', 'person_occupant', 'highway', 'northbound', 8.0, 6.0, 1.0),
    Case('person_north_late', 'person_occupant', 'highway', 'northbound', 8.0, 6.0, 4.0),
    Case('person_south_early', 'person_occupant', 'highway', 'southbound', 8.0, 6.0, 1.0),
    Case('person_south_late', 'person_occupant', 'highway', 'southbound', 8.0, 6.0, 4.0),
    Case('property_near', 'property', 'highway', 'northbound', 8.0, 6.0, 1.0),
    Case('property_far', 'property', 'highway', 'northbound', 8.0, 6.0, 1.0),
    Case('premises_person_early', 'person_occupant', 'public_access_premises', 'northbound', 8.0, 6.0, 1.0),
    Case('premises_person_late', 'person_occupant', 'public_access_premises', 'northbound', 8.0, 6.0, 4.0),
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_site(site: Mapping) -> None:
    """Validate actual map/source readback before any actor is spawned."""
    _require(site.get('cell_id') == 'C111304', 'wrong cell')
    _require(site.get('layout') == 'intersection', 'wrong layout')
    _require(site.get('public_access_basis') in ('highway', 'public_access_premises'), 'public access not sourced')
    _require(bool(site.get('public_access_source_sha256')), 'public access source missing')
    lanes = site.get('lanes', {})
    for direction in ('northbound', 'southbound', 'crossing'):
        lane = lanes.get(direction, {})
        _require(lane.get('source_sha256') and lane.get('lane_id') and len(lane.get('waypoints', [])) >= 2,
                 f'{direction} lane source missing')
    _require(lanes['northbound']['lane_id'] != lanes['southbound']['lane_id'], 'approaches share lane')
    _require(site.get('conflict_zone', {}).get('source_sha256'), 'conflict zone source missing')
    _require(site.get('property_anchor', {}).get('source_sha256'), 'property anchor source missing')
    _require(site.get('crossing_occupant', {}).get('source_sha256'), 'fixed occupant source missing')


def build_case(adapter, site: Mapping, case: Case):
    """Spawn two moving vehicles and an identified occupant/property with cleanup."""
    validate_site(site)
    _require(case in CASES, 'unknown case')
    _require(site['public_access_basis'] == case.public_access_basis, 'site basis differs from case')
    lanes = site['lanes']
    owned = []
    try:
        ego = adapter.spawn_vehicle(lanes[case.approach]['waypoints'][0], role='ego')
        _require(ego is not None, 'ego spawn failed')
        owned.append(ego)
        crossing = adapter.spawn_vehicle(lanes['crossing']['waypoints'][0], role='crossing')
        _require(crossing is not None, 'crossing vehicle spawn failed')
        owned.append(crossing)
        occupant = adapter.register_occupant(crossing, site['crossing_occupant'])
        _require(occupant is not None, 'crossing occupant registration failed')
        property_obj = adapter.spawn_property(site['property_anchor'], offset_m=0.0 if case.case_id == 'property_near' else 8.0)
        _require(property_obj is not None, 'property spawn failed')
        owned.append(property_obj)
        adapter.set_route(ego, lanes[case.approach]['waypoints'], target_speed_mps=case.ego_speed_mps)
        adapter.set_route(crossing, lanes['crossing']['waypoints'], target_speed_mps=case.crossing_speed_mps,
                          release_s=case.crossing_release_s)
        return {'ego': ego, 'crossing_vehicle': crossing, 'occupant': occupant,
                'property': property_obj, 'owned': tuple(owned), 'case_id': case.case_id}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_history(rows: list[Mapping], case: Case) -> dict:
    """Read original synchronized actor positions; reject inferred or missing rows."""
    _require(case in CASES, 'unknown case')
    _require(len(rows) >= 2, 'original history too short')
    previous_frame = None
    nearest_person = float('inf')
    nearest_property = float('inf')
    ego_speeds = []
    crossing_speeds = []
    for row in rows:
        frame = row.get('original_frame')
        _require(type(frame) is int and (previous_frame is None or frame == previous_frame + 1),
                 'original frame discontinuity')
        previous_frame = frame
        _require(row.get('source_sha256') and row.get('map_source_sha256'), 'original source missing')
        _require(row.get('ego_id') and row.get('crossing_vehicle_id') and row.get('occupant_id')
                 and row.get('property_id'), 'actor identity missing')
        _require(row.get('occupant_vehicle_id') == row['crossing_vehicle_id'], 'occupant is not in crossing vehicle')
        for key in ('ego_xy', 'occupant_xy', 'property_xy'):
            _require(isinstance(row.get(key), list) and len(row[key]) == 2
                     and all(isinstance(v, (int, float)) and isfinite(v) for v in row[key]),
                     f'{key} missing or invalid')
        for key, target in (('ego_speed_mps', ego_speeds), ('crossing_speed_mps', crossing_speeds)):
            value = row.get(key)
            _require(isinstance(value, (int, float)) and isfinite(value) and value >= 0, f'{key} missing')
            target.append(value)
        nearest_person = min(nearest_person, hypot(row['ego_xy'][0]-row['occupant_xy'][0],
                                                    row['ego_xy'][1]-row['occupant_xy'][1]))
        nearest_property = min(nearest_property, hypot(row['ego_xy'][0]-row['property_xy'][0],
                                                      row['ego_xy'][1]-row['property_xy'][1]))
    return {'case_id': case.case_id, 'first_original_frame': rows[0]['original_frame'],
            'last_original_frame': previous_frame, 'frame_count': len(rows),
            'min_ego_occupant_center_distance_m': nearest_person,
            'min_ego_property_center_distance_m': nearest_property,
            'ego_speed_mps_history': ego_speeds, 'crossing_speed_mps_history': crossing_speeds,
            'legal_judgment': None}


def audit_pair(left: Mapping, right: Mapping, differing: set[str]) -> None:
    """Fail closed on missing original measurements or changed fixed conditions."""
    required = {'case_id', 'site_sha256', 'map_sha256', 'public_access_basis', 'ego_route_sha256',
                'crossing_route_sha256', 'ego_blueprint', 'crossing_blueprint', 'occupant_id',
                'property_blueprint', 'weather_sha256', 'camera_plan_sha256', 'duration_frames',
                'original_history_sha256', 'min_ego_occupant_center_distance_m',
                'min_ego_property_center_distance_m'}
    for side in (left, right):
        _require(required <= side.keys() and all(side[k] is not None for k in required), 'comparison source missing')
        _require(side['duration_frames'] == 900, 'duration changed')
    fixed = required - differing - {'case_id', 'original_history_sha256',
                                     'min_ego_occupant_center_distance_m',
                                     'min_ego_property_center_distance_m'}
    for key in fixed:
        _require(left[key] == right[key], f'fixed condition changed: {key}')
    _require(left['case_id'] != right['case_id'], 'same case twice')
    for key in differing:
        _require(key in left and key in right and left[key] is not None and right[key] is not None,
                 f'deliberate difference source missing: {key}')
        _require(left[key] != right[key], f'deliberate difference absent: {key}')
