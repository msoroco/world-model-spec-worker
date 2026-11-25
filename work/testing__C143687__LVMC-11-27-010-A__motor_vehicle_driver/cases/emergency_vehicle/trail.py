"""Source-gated trail construction for LVMC 11.27.010(A) at C143687.

Administrative trail designation and dedication are supplied as reviewed records.
The simulator constructs travel and a sign; it cannot create those legal facts.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    name: str
    designated: bool
    dedicated: bool
    prohibition_posted: bool
    emergency_use: bool = False
    maintenance_use: bool = False


CASES = (
    Case('all_prerequisites', True, True, True),
    Case('not_designated', False, True, True),
    Case('not_dedicated', True, False, True),
    Case('no_prohibition_sign', True, True, False),
    Case('emergency_vehicle', True, True, True, emergency_use=True),
    Case('maintenance_vehicle', True, True, True, maintenance_use=True),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _point(value) -> bool:
    return isinstance(value, (tuple, list)) and len(value) == 2 and all(
        type(v) in (int, float) and isfinite(v) for v in value
    )


def _inside(point, box) -> bool:
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def validate_source(site: Mapping, case: Case) -> None:
    """Reject a catalog label or sign flag without the corresponding source readback."""
    require(case in CASES, 'unknown exact case')
    require(site.get('cell_id') == 'C143687' and site.get('layout') == 'nonmotorized_trail',
            'wrong trail cell or layout')
    require(bool(site.get('map_sha256')) and bool(site.get('corridor_source_sha256')),
            'trail map or corridor source missing')
    box = site.get('corridor_box_xy')
    require(isinstance(box, (tuple, list)) and len(box) == 4 and
            all(type(v) in (int, float) and isfinite(v) for v in box) and
            box[0] < box[2] and box[1] < box[3], 'corridor bounds missing')
    route = site.get('route_xy')
    require(isinstance(route, (tuple, list)) and len(route) >= 3 and
            all(_point(p) and _inside(p, box) for p in route),
            'motor route not proven inside corridor')
    require(len({tuple(p) for p in route}) > 1, 'stationary route')
    records = site.get('administrative_records', {})
    for key, expected in (('official_plan_designation', case.designated),
                          ('city_trail_dedication', case.dedicated)):
        record = records.get(key, {})
        require(record.get('source_sha256') and type(record.get('asserted')) is bool,
                f'{key} affirmative source missing')
        require(record['asserted'] is expected, f'{key} differs from case')
    sign = site.get('sign', {})
    require(sign.get('source_sha256') and sign.get('governed_access_sha256') and
            _point(sign.get('position_xy')) and sign.get('face_readback_sha256') and
            isinstance(sign.get('face_text'), str) and sign['face_text'].strip(),
            'sign source, face, or access relation missing')
    require(type(sign.get('prohibits_motor_vehicles')) is bool and
            sign['prohibits_motor_vehicles'] is case.prohibition_posted,
            'prohibition sign content differs from case')
    require(_inside(sign['position_xy'], box), 'sign is outside governed corridor')
    require(site.get('vehicle_blueprint') and site.get('vehicle_class_source_sha256') and
            site.get('operator_source_sha256'), 'vehicle or operator source missing')
    require(type(site.get('target_speed_mps')) in (int, float) and
            isfinite(site['target_speed_mps']) and site['target_speed_mps'] > 0,
            'travel speed command missing')
    require(site.get('exception_status_source_sha256'), 'exception source missing')
    require(site.get('emergency_use') is case.emergency_use and
            site.get('maintenance_use') is case.maintenance_use,
            'exception use differs from case')
    require(not (case.emergency_use and case.maintenance_use), 'exceptions must be isolated')


def build_case(adapter, site: Mapping, case: Case):
    """Create a motorized traversal and governed physical sign with local cleanup."""
    validate_source(site, case)
    owned = []
    try:
        sign = adapter.install_sign(site['sign']['position_xy'], site['sign']['face_text'],
                                    governed_access_sha256=site['sign']['governed_access_sha256'])
        require(sign is not None, 'sign construction failed')
        owned.append(sign)
        vehicle = adapter.spawn_vehicle(site['route_xy'][0], site['vehicle_blueprint'],
                                        role='ego')
        require(vehicle is not None, 'motor vehicle construction failed')
        owned.append(vehicle)
        adapter.set_route(vehicle, site['route_xy'], target_speed_mps=site['target_speed_mps'])
        adapter.bind_status(vehicle, emergency_use=case.emergency_use,
                            maintenance_use=case.maintenance_use,
                            status_source_sha256=site['exception_status_source_sha256'])
        return {'case': case.name, 'vehicle': vehicle, 'sign': sign,
                'owned': tuple(owned), 'admin_records': site['administrative_records']}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise
