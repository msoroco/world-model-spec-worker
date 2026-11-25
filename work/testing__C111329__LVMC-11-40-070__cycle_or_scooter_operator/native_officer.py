"""Lazy Native Police Officer actor and command source adapter.

The local operator must supply a reviewed authority packet and a visible gesture
asset. This code refuses a mere callback label as evidence of an officer command.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


RECIPIENT_ROLE = "selected_cycle_operator"


def route_digest(site: dict) -> str:
    return hashlib.sha256(json.dumps(site["vehicle_route"], sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def read_officer_source(path: Path, expected_sha256: str, site: dict) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("original officer source hash mismatch")
    packet = json.loads(raw)
    required = ("source_kind", "map_name", "authority_source", "officer_blueprint_id",
                "gesture_asset_id", "spawn_xyz", "recipient_role",
                "recipient_route_sha256", "command",
                "start_frame", "end_frame", "visible_camera_ids")
    if any(k not in packet for k in required):
        raise ValueError("incomplete original officer source")
    if packet["source_kind"] != "original_local_officer_authority_and_gesture":
        raise ValueError("unverified original officer source")
    if packet["map_name"] != site["map_name"] or packet["authority_source"] != site.get("police_authority_source"):
        raise ValueError("officer map or authority source mismatch")
    if (packet["recipient_role"] != RECIPIENT_ROLE or
            packet["recipient_route_sha256"] != route_digest(site)):
        raise ValueError("officer recipient role or route source mismatch")
    if packet["command"] not in {"stop", "proceed"}:
        raise ValueError("unsupported original officer command")
    if not isinstance(packet["spawn_xyz"], list) or len(packet["spawn_xyz"]) != 3:
        raise ValueError("invalid officer spawn pose")
    if not isinstance(packet["start_frame"], int) or not isinstance(packet["end_frame"], int) or packet["start_frame"] >= packet["end_frame"]:
        raise ValueError("invalid officer command window")
    if len(set(packet["visible_camera_ids"])) < 2:
        raise ValueError("officer gesture has insufficient camera plan")
    return packet


def bind_recipient(packet: dict, bike, site: dict) -> dict:
    """Bind the reviewed role and route to the observed spawned actor id."""
    if (packet["recipient_role"] != RECIPIENT_ROLE or
            packet["recipient_route_sha256"] != route_digest(site) or
            not bike.is_alive or not str(bike.id)):
        raise ValueError("officer live recipient binding mismatch")
    bound = dict(packet)
    bound["observed_recipient_bike_id"] = str(bike.id)
    return bound


def construct(world, carla, packet: dict, case: dict, gesture_adapter) -> dict:
    """Spawn actor, read it back, and install a real gesture control adapter."""
    if case["officer_direction"] != packet["command"]:
        raise ValueError("officer command differs from exact case")
    if world.get_map().name != packet["map_name"]:
        raise ValueError("officer Native map readback mismatch")
    if not callable(gesture_adapter):
        raise ValueError("visible officer gesture adapter required")
    blueprint = world.get_blueprint_library().find(packet["officer_blueprint_id"])
    if blueprint is None or blueprint.id != packet["officer_blueprint_id"]:
        raise ValueError("officer blueprint unavailable")
    x, y, z = map(float, packet["spawn_xyz"])
    pose = carla.Transform(carla.Location(x=x, y=y, z=z))
    officer = world.spawn_actor(blueprint, pose)
    if officer is None:
        raise RuntimeError("officer actor spawn failed")
    try:
        if not officer.is_alive or officer.type_id != blueprint.id or officer.get_transform().location.distance(pose.location) > 1.0:
            raise ValueError("officer actor readback mismatch")
        gesture_adapter(officer, packet["gesture_asset_id"], packet["command"])
        return {"officer": officer, "owned_actors": [officer], "packet": packet}
    except BaseException:
        officer.destroy()
        raise


def read_command(officer, packet: dict, frame: int, gesture_reader, bike_id: str) -> dict:
    if not officer.is_alive or not callable(gesture_reader):
        raise ValueError("original officer actor or gesture reader unavailable")
    if str(bike_id) != packet.get("observed_recipient_bike_id"):
        raise ValueError("officer command recipient mismatch")
    active = packet["start_frame"] <= frame <= packet["end_frame"]
    observed = gesture_reader(officer, packet["gesture_asset_id"], frame)
    if active and observed != packet["command"]:
        raise ValueError("visible officer gesture readback missing")
    if not active and observed != "none":
        raise ValueError("officer gesture outside source window")
    return {"actor_id": str(officer.id), "authority_source": packet["authority_source"],
            "recipient_id": str(bike_id), "command": observed,
            "gesture_asset_id": packet["gesture_asset_id"], "frame": frame,
            "source_kind": "original_native_officer_readback"}
