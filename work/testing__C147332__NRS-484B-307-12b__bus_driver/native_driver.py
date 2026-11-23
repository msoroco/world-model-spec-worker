"""Lazy CARLA actor placement and closed-loop bus control requests."""
from __future__ import annotations

import math

from bus_route import ADJACENT_LANE_Y, GOVERNED_LANE_Y, ROUTES


def _clamp(value, low, high):
    return min(high, max(low, value))


def control_request(scene, *, x_m, y_m, yaw_deg, speed_mps):
    """Compute a steering/speed request from current measured Native state."""
    kind = scene["route"]["route_kind"]
    if kind not in ROUTES:
        raise ValueError("unknown exact bus controller")
    if kind == "red_lane_stand":
        return {"throttle": 0.0, "brake": 1.0, "steer": 0.0,
                "target_speed_mps": 0.0, "target_lateral_m": GOVERNED_LANE_Y}
    if kind == "adjacent_travel":
        target_y = ADJACENT_LANE_Y
    elif kind == "red_lane_drive":
        target_y = GOVERNED_LANE_Y
    else:
        # The lateral transition has fixed 16 m longitudinal extent. Smooth
        # interpolation avoids an instantaneous lane-center jump.
        fraction = _clamp((x_m - 37.0) / 16.0, 0.0, 1.0)
        blend = fraction * fraction * (3 - 2 * fraction)
        target_y = ADJACENT_LANE_Y + blend * (GOVERNED_LANE_Y - ADJACENT_LANE_Y)
    target_x = max(x_m + 8.0, 8.0)
    target_heading = math.degrees(math.atan2(target_y - y_m, target_x - x_m))
    heading_error = (target_heading - yaw_deg + 180) % 360 - 180
    steer = _clamp(heading_error / 35.0, -0.65, 0.65)
    target_speed = 8.0
    speed_error = target_speed - max(0.0, speed_mps)
    return {"throttle": _clamp(speed_error * 0.18, 0.0, 0.55),
            "brake": _clamp(-speed_error * 0.2, 0.0, 0.6),
            "steer": steer, "target_speed_mps": target_speed,
            "target_lateral_m": target_y}


def spawn_scene(world, scene, carla, site):
    """Spawn the exact reviewed sign asset and a bus; never substitute assets."""
    library = world.get_blueprint_library()
    bus_id = scene.get("bus_blueprint_id")
    sign_id = site.get("native_asset_blueprint_id")
    if not bus_id or not sign_id:
        raise ValueError("exact bus and reviewed red-X asset IDs required")
    bus_bp = library.find(bus_id)
    sign_bp = library.find(sign_id)
    if bus_bp is None or sign_bp is None:
        raise ValueError("exact bus or reviewed red-X asset unavailable")
    state = site["native_display_state"]
    attribute, value = state["attribute"], state["red_x_value"]
    if not sign_bp.has_attribute(attribute):
        raise ValueError("reviewed red-X display attribute unavailable on blueprint")
    sign_bp.set_attribute(attribute, value)
    if str(sign_bp.get_attribute(attribute)) != value:
        raise ValueError("red-X blueprint display state did not read back")
    signal = scene["signal"]
    sign_transform = carla.Transform(
        carla.Location(x=signal["longitudinal_m"], y=signal["lateral_m"],
                       z=signal["height_m"]), carla.Rotation(yaw=180.0))
    head = world.spawn_actor(sign_bp, sign_transform)
    if head is None:
        raise RuntimeError("reviewed red-X head spawn failed")
    if str(head.attributes.get(attribute)) != value:
        head.destroy()
        raise ValueError("spawned red-X head display state did not read back")
    x, y = scene["route"]["waypoint_centers_m"][0]
    try:
        bus = world.spawn_actor(bus_bp, carla.Transform(
            carla.Location(x=x, y=y, z=0.7), carla.Rotation(yaw=0.0)))
        if bus is None:
            raise RuntimeError("exact bus spawn failed")
        extent = bus.bounding_box.extent
        if extent.x < 2.5 or extent.y < 1.0 or extent.y >= 1.8:
            raise ValueError("Native actor footprint is not a lane-fitting bus")
        return bus, head
    except BaseException:
        head.destroy()
        raise


def apply_request(bus, scene, carla):
    transform = bus.get_transform()
    velocity = bus.get_velocity()
    speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
    request = control_request(scene, x_m=transform.location.x,
                              y_m=transform.location.y,
                              yaw_deg=transform.rotation.yaw, speed_mps=speed)
    bus.apply_control(carla.VehicleControl(throttle=request["throttle"],
                                           brake=request["brake"], steer=request["steer"]))
    return request
