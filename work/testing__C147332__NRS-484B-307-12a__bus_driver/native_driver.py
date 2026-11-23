"""Closed-loop bus controls and two-head placement; CARLA is imported lazily."""
from __future__ import annotations

import math


def clamp(value, low, high):
    return max(low, min(high, value))


def control_request(scene, *, x_m, y_m, yaw_deg, speed_mps):
    kind = scene["case_id"].rsplit("__", 1)[-1]
    target_y = -5.4 if scene["bus_lane_id"] == "west" else -1.8
    if kind == "green_selected_stand":
        return {"throttle": 0.0, "brake": 1.0, "steer": 0.0,
                "target_speed_mps": 0.0, "target_lateral_m": target_y}
    if kind not in ("green_selected_drive", "adjacent_dark_drive", "second_green_drive"):
        raise ValueError("unknown green-arrow controller")
    heading = math.degrees(math.atan2(target_y - y_m, 8.0))
    error = (heading - yaw_deg + 180) % 360 - 180
    speed_error = 8.0 - max(0.0, speed_mps)
    return {"throttle": clamp(speed_error * 0.18, 0.0, 0.55),
            "brake": clamp(-speed_error * 0.2, 0.0, 0.6),
            "steer": clamp(error / 35.0, -0.65, 0.65),
            "target_speed_mps": 8.0, "target_lateral_m": target_y}


def spawn_scene(world, scene, carla, site):
    library = world.get_blueprint_library()
    bus_bp = library.find(scene["bus_blueprint_id"])
    if bus_bp is None:
        raise ValueError("exact bus blueprint unavailable")
    heads = []
    try:
        for signal in scene["signals"]:
            key = ("native_asset_blueprint_id" if signal["display"] == "down_green_arrow"
                   else "dark_asset_blueprint_id")
            identifier = site.get(key)
            if not identifier:
                raise ValueError("reviewed green and dark head assets required")
            blueprint = library.find(identifier)
            if blueprint is None:
                raise ValueError("exact overhead head asset unavailable")
            state = site["native_display_state"]
            attribute = state["attribute"]
            value = state["green_value"] if signal["display"] == "down_green_arrow" else state["dark_value"]
            if not blueprint.has_attribute(attribute):
                raise ValueError("reviewed display attribute unavailable on head blueprint")
            blueprint.set_attribute(attribute, value)
            if str(blueprint.get_attribute(attribute)) != value:
                raise ValueError("head blueprint display state did not read back")
            transform = carla.Transform(carla.Location(x=signal["longitudinal_m"],
                y=signal["lateral_m"], z=signal["height_m"]), carla.Rotation(yaw=180))
            actor = world.spawn_actor(blueprint, transform)
            if actor is None:
                raise RuntimeError("overhead head spawn failed")
            heads.append(actor)
            if str(actor.attributes.get(attribute)) != value:
                raise ValueError("spawned overhead head display state did not read back")
        x, y = scene["route_waypoint_centers_m"][0]
        bus = world.spawn_actor(bus_bp, carla.Transform(carla.Location(x=x, y=y, z=0.7),
                                                         carla.Rotation(yaw=0)))
        if bus is None:
            raise RuntimeError("exact bus spawn failed")
        extent = bus.bounding_box.extent
        if extent.x < 2.5 or extent.y < 1.0 or extent.y >= 1.8:
            bus.destroy()
            raise ValueError("Native actor footprint is not a lane-fitting bus")
        return bus, heads
    except BaseException:
        for head in reversed(heads):
            head.destroy()
        raise


def apply_request(bus, scene, carla):
    transform = bus.get_transform()
    velocity = bus.get_velocity()
    speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
    request = control_request(scene, x_m=transform.location.x,
        y_m=transform.location.y, yaw_deg=transform.rotation.yaw, speed_mps=speed)
    bus.apply_control(carla.VehicleControl(throttle=request["throttle"],
                                           brake=request["brake"], steer=request["steer"]))
    return request
