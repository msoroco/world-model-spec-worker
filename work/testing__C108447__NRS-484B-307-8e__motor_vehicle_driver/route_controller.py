"""Lazy CARLA route follower for an original source-bound property connector.

The connector points are map coordinates from a reviewed packet, never generated
by a case label. Capture must still measure actual body path and device states.
"""
from __future__ import annotations

import math
from typing import Any


def validate_route(packet: dict[str, Any], property_id: str) -> list[tuple[float, float]]:
    source = packet.get('source', {})
    if source.get('kind') != 'original_native_map_and_property_authority' or not source.get('sha256'):
        raise ValueError('original map/property authority source required')
    parcel = next((p for p in packet.get('properties', []) if p.get('id') == property_id), None)
    if parcel is None or parcel.get('status') not in ('public', 'private') or not parcel.get('authority'):
        raise ValueError('original classified property required')
    route = packet.get('connector_routes', {}).get(property_id)
    if not route or len(route) < 3 or not all(len(v) == 2 and all(math.isfinite(float(q)) for q in v) for v in route):
        raise ValueError('source-bound connector route with at least three finite points required')
    from property_route import _traversed_property_ids
    samples = [{'x': x, 'y': y} for x, y in route]
    if property_id not in _traversed_property_ids(samples, [parcel]):
        raise ValueError('connector does not traverse classified property')
    if math.dist(route[0], route[-1]) < 1:
        raise ValueError('connector endpoints collapse')
    return [(float(x), float(y)) for x, y in route]


def steering_command(position_xy: tuple[float, float], yaw_rad: float, target_xy: tuple[float, float], speed_mps: float, target_speed_mps: float = 5.0) -> dict[str, float]:
    """Return bounded low-speed steering/throttle/brake commands; not proof of motion."""
    if any(not math.isfinite(x) for x in (*position_xy, yaw_rad, *target_xy, speed_mps, target_speed_mps)):
        raise ValueError('finite route/controller inputs required')
    if target_speed_mps <= 0 or target_speed_mps > 8:
        raise ValueError('low-speed route target required')
    angle = math.atan2(target_xy[1] - position_xy[1], target_xy[0] - position_xy[0]) - yaw_rad
    angle = math.atan2(math.sin(angle), math.cos(angle))
    steer = max(-1.0, min(1.0, 1.5 * angle))
    error = target_speed_mps - speed_mps
    return {'steer': steer, 'throttle': max(0.0, min(0.4, 0.15 * error)), 'brake': max(0.0, min(0.5, -0.2 * error))}


def apply_carla_control(vehicle: Any, command: dict[str, float]) -> None:
    import carla  # lazy: CPU import and proof do not require the simulator
    vehicle.apply_control(carla.VehicleControl(**command))
