"""Bind and sample original signal actors for C227824 pedestrian entry.

The scene must supply a reviewed, source-hashed inventory of every device that
governs this route. Actor metadata and readback are required; CARLA's bare Red
state does not prove a steady red signal alone or pedestrian authority.
"""
from __future__ import annotations

import math


DEVICES = {"walk", "flashing_hand_countdown", "flashing_hand_no_countdown",
           "steady_hand"}


def _state(actor):
    return str(actor.get_state()).split(".")[-1].lower()


def _review(scene):
    review = scene.get("device_inventory_review")
    if not isinstance(review, dict) or review.get("complete") is not True:
        raise ValueError("complete governing-device review missing")
    digest = review.get("source_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("governing-device review source hash missing")
    route = scene.get("route_id")
    if not isinstance(route, str) or not route:
        raise ValueError("pedestrian route identity missing")
    ids = scene.get("governing_pedestrian_device_ids")
    if not isinstance(ids, list) or len(ids) != len(set(ids)) or any(type(i) is not int or i < 0 for i in ids):
        raise ValueError("governing-device inventory invalid")
    head_id = scene.get("facing_head_id")
    if type(head_id) is not int or head_id < 0 or head_id in ids:
        raise ValueError("facing traffic signal identity invalid")
    return route, ids, head_id


def bind(world, scene):
    """Resolve exact original actors and require route/authority metadata."""
    route, ids, head_id = _review(scene)
    head = world.get_actor(head_id)
    if head is None or head.attributes.get("official_traffic_signal") != "true" or head.attributes.get("governs_pedestrian_route_id") != route:
        raise ValueError("official route-facing traffic head absent")
    if head.attributes.get("signal_shape") != "circle" or head.attributes.get("sole_illuminated") != "true":
        raise ValueError("source asset does not establish red alone")
    others = []
    for actor_id in ids:
        actor = world.get_actor(actor_id)
        if actor is None or actor.attributes.get("official_pedestrian_signal") != "true" or actor.attributes.get("governs_pedestrian_route_id") != route:
            raise ValueError("reviewed official pedestrian device absent")
        others.append(actor)
    return head, others


def configure(head, others, scene, carla):
    """Request red alone and a specified other indication, then read back."""
    _, ids, _ = _review(scene)
    requested = scene.get("requested_pedestrian_indication")
    if requested not in DEVICES | {"none"}:
        raise ValueError("unsupported pedestrian indication")
    if (requested == "none") != (len(ids) == 0):
        raise ValueError("requested indication disagrees with reviewed device inventory")
    head.set_state(carla.TrafficLightState.Red)
    head.freeze(True)
    if _state(head) != "red":
        raise ValueError("traffic head did not read back red")
    if requested != "none":
        if len(others) != 1 or not callable(getattr(others[0], "set_pedestrian_indication", None)):
            raise ValueError("source-backed pedestrian indication driver unavailable")
        others[0].set_pedestrian_indication(requested)
        if _state(others[0]) != requested:
            raise ValueError("pedestrian indication did not read back")
    return {"facing_head_id": head.id, "other_device_ids": [actor.id for actor in others],
            "requested_pedestrian_indication": requested,
            "original_readback_confirmed": True, "actual_pixels_verified": False}


def sample(head, others, scene, *, frame, time_s):
    """Return source packets for the same original world snapshot/frame."""
    route, ids, head_id = _review(scene)
    if type(frame) is not int or frame < 0 or not isinstance(time_s, (int, float)) or not math.isfinite(time_s):
        raise ValueError("invalid original signal frame")
    if head.id != head_id or [actor.id for actor in others] != ids:
        raise ValueError("original signal actors changed")
    if _state(head) != "red":
        raise ValueError("facing traffic head not red in original frame")
    common = {"case_id": scene["case_id"], "frame": frame, "time_s": float(time_s)}
    signal = {**common, "facing_traffic_signal": {
        "official": True, "indication": "steady_red_alone",
        "head_id": head.id, "route_id": route,
        "asset_source_sha256": scene["device_inventory_review"]["source_sha256"]}}
    devices = []
    for actor in others:
        indication = _state(actor)
        if indication not in DEVICES:
            raise ValueError("unsupported original pedestrian device state")
        device = {"official": True, "indication": indication, "head_id": actor.id,
                  "route_id": route}
        if indication == "flashing_hand_countdown":
            get_countdown = getattr(actor, "get_countdown", None)
            if not callable(get_countdown):
                raise ValueError("original pedestrian countdown readback unavailable")
            count = get_countdown()
            if not isinstance(count, (int, float)) or not math.isfinite(count) or count < 0:
                raise ValueError("invalid original pedestrian countdown")
            device["countdown_s"] = float(count)
        devices.append(device)
    return signal, {**common, "other_devices": devices}
