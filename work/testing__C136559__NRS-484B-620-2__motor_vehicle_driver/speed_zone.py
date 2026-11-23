"""Source-gated C136559 signed-zone construction and original-frame audit.

Targets are engineering requests. Measured speed, zone occupancy and sign status
are retained independently; this module never decides statutory compliance.
"""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    case_id: str
    direction: str
    requested_mph: float
    zone_mode: str


CASES = (
    Case('signed_below', 'eastbound', 20.0, 'established_signed'),
    Case('signed_near', 'eastbound', 24.5, 'established_signed'),
    Case('signed_above', 'eastbound', 30.0, 'established_signed'),
    Case('outside_zone', 'eastbound', 30.0, 'outside'),
    Case('sign_not_installed', 'eastbound', 30.0, 'sign_absent'),
    Case('westbound_signed', 'westbound', 30.0, 'established_signed'),
)
LIMIT_MPH = 25.0  # authored zone instruction, never a general statutory limit


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def validate_site(site: Mapping, case: Case) -> None:
    require(case in CASES, 'unknown case')
    require(site.get('cell_id') == 'C136559' and site.get('layout') == 'narrow_road', 'wrong site')
    require(site.get('road_source_sha256') and site.get('zone_establishment_source_sha256'), 'road or zone source missing')
    require(site.get('public_access_source_sha256') and site.get('boundary_source_sha256'), 'public road boundary source missing')
    require(site.get('authorized_speed_mph') == LIMIT_MPH, 'authorized speed changed')
    require(site.get('zone_extent_source_sha256') and site.get('sign_instruction_source_sha256'), 'zone or sign instruction source missing')
    lanes = site.get('lanes', {})
    for direction in ('eastbound', 'westbound'):
        lane = lanes.get(direction, {})
        require(lane.get('lane_id') and lane.get('source_sha256') and len(lane.get('waypoints', [])) >= 2,
                f'{direction} route source missing')
    require(lanes['eastbound']['lane_id'] != lanes['westbound']['lane_id'], 'directions share lane')
    signs = site.get('signs', {})
    require(signs.get(case.direction, {}).get('source_sha256'), 'governing sign source missing')
    require(site.get('vehicle_class') == 'self_propelled_nonrail_motor_vehicle', 'qualifying vehicle missing')


def build_case(adapter, site: Mapping, case: Case):
    """Create route and sign readback; CARLA remains lazy behind adapter."""
    validate_site(site, case)
    lane = site['lanes'][case.direction]
    owned = []
    try:
        ego = adapter.spawn_vehicle(lane['waypoints'][0], role='ego', vehicle_class=site['vehicle_class'])
        require(ego is not None, 'ego spawn failed')
        owned.append(ego)
        sign = adapter.install_sign(site['signs'][case.direction], enabled=case.zone_mode != 'sign_absent')
        require(sign is not None, 'sign operation failed')
        owned.append(sign)
        readback = adapter.read_sign(sign)
        require(readback.get('source_sha256') and readback.get('direction') == case.direction,
                'sign readback missing or wrong direction')
        require(bool(readback.get('installed')) == (case.zone_mode != 'sign_absent'), 'sign installation mismatch')
        adapter.set_route(ego, lane['waypoints'], target_speed_mps=case.requested_mph * 0.44704,
                          zone_mode=case.zone_mode)
        return {'case_id': case.case_id, 'ego': ego, 'sign': sign, 'owned': tuple(owned),
                'sign_readback': readback}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], case: Case) -> dict:
    """Retain each measured speed and applicability source without classifying a verdict."""
    require(case in CASES and len(rows) >= 2, 'original history missing')
    previous = None
    prior_time = None
    speeds = []
    inside = []
    installed = []
    for row in rows:
        frame = row.get('original_frame')
        time = row.get('original_time_s')
        require(type(frame) is int and (previous is None or frame == previous + 1), 'original frame discontinuity')
        require(isinstance(time, (float, int)) and isfinite(time) and
                (prior_time is None or time > prior_time), 'original time discontinuity')
        require(row.get('source_sha256') and row.get('zone_establishment_source_sha256') and
                row.get('zone_extent_source_sha256') and row.get('sign_readback_source_sha256') and
                row.get('map_source_sha256'), 'original source missing')
        require(row.get('ego_id') and row.get('vehicle_class') == 'self_propelled_nonrail_motor_vehicle',
                'vehicle identity missing')
        require(row.get('direction') == case.direction and row.get('sign_direction') == case.direction,
                'governing direction mismatch')
        speed = row.get('actual_speed_mps')
        require(isinstance(speed, (float, int)) and isfinite(speed) and speed >= 0,
                'actual speed missing')
        require(type(row.get('inside_zone')) is bool and type(row.get('sign_installed')) is bool,
                'occupancy or sign readback missing')
        speeds.append(speed)
        inside.append(row['inside_zone'])
        installed.append(row['sign_installed'])
        previous, prior_time = frame, time
    return {'case_id': case.case_id, 'first_original_frame': rows[0]['original_frame'],
            'last_original_frame': previous, 'frame_count': len(rows),
            'actual_speed_mps_history': speeds, 'inside_zone_history': inside,
            'sign_installed_history': installed, 'authorized_speed_mph': LIMIT_MPH,
            'zone_establishment_source_sha256': rows[0]['zone_establishment_source_sha256'],
            'sign_appropriateness_judgment': None, 'legal_judgment': None}


def audit_pair(left: Mapping, right: Mapping, deliberate: set[str]) -> None:
    required = {'case_id', 'road_source_sha256', 'map_source_sha256',
                'zone_establishment_source_sha256', 'zone_extent_source_sha256',
                'sign_instruction_source_sha256', 'ego_blueprint', 'weather_sha256',
                'camera_plan_sha256', 'duration_frames', 'requested_mph', 'zone_mode',
                'direction', 'original_history_sha256'}
    for side in (left, right):
        require(required <= side.keys() and all(side[k] is not None for k in required),
                'comparison source missing')
        require(side['duration_frames'] == 900, 'duration changed')
    require(left['case_id'] != right['case_id'], 'same case twice')
    fixed = required - deliberate - {'case_id', 'original_history_sha256'}
    for key in fixed:
        require(left[key] == right[key], f'fixed condition changed: {key}')
    for key in deliberate:
        require(key in required and left[key] != right[key], f'deliberate difference absent: {key}')
