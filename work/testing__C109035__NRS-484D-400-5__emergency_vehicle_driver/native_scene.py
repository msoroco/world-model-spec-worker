"""Source-gated Native spawn adapter for the emergency-response intersection.

The scene packet is a local reviewer artifact. Without it, no actor is spawned.
CARLA is passed in at invocation and never imported for CPU tests.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from emergency_scene import scene_geometry


def validate_site(packet_path: Path, *, case_id: str, map_opendrive: str) -> dict:
    packet = json.loads(Path(packet_path).read_text())
    if packet.get("case_id") != case_id or packet.get("cell_id") != "C109035" or packet.get("actor") != "emergency_vehicle_driver":
        raise ValueError("Reviewed packet identity mismatch")
    if not packet.get("reviewer") or not packet.get("source_citation"):
        raise ValueError("Reviewed site or original source citation missing")
    if packet.get("opendrive_sha256") != hashlib.sha256(map_opendrive.encode()).hexdigest():
        raise ValueError("Reviewed OpenDRIVE map hash mismatch")
    direction = packet.get("approach")
    reference = scene_geometry(direction, packet.get("intersection_station_m", 0.0))
    if packet.get("pedestrian_role") != reference["pedestrian_role"]:
        raise ValueError("Pedestrian recipient role mismatch")
    for key in ("ego_blueprint_id", "pedestrian_blueprint_id", "ego_transform", "pedestrian_transform"):
        if not packet.get(key):
            raise ValueError("Reviewed spawn packet missing: " + key)
    ex, ey = packet["ego_transform"]["location"][:2]
    px, py = packet["pedestrian_transform"]["location"][:2]
    if abs(ex - reference["ego_spawn_xy_m"][0]) > 1.0 or abs(ey - reference["ego_spawn_xy_m"][1]) > 1.0:
        raise ValueError("Ego route position differs from reviewed engineering geometry")
    if abs(px - reference["pedestrian_spawn_xy_m"][0]) > 1.0 or abs(py - reference["pedestrian_spawn_xy_m"][1]) > 1.0:
        raise ValueError("Pedestrian recipient position differs from reviewed engineering geometry")
    return packet


def create(world, carla_api, packet_path: Path, case_id: str):
    packet = validate_site(packet_path, case_id=case_id, map_opendrive=world.get_map().to_opendrive())
    def transform(item):
        x, y, z = item["location"]
        pitch, yaw, roll = item["rotation"]
        return carla_api.Transform(carla_api.Location(x, y, z), carla_api.Rotation(pitch, yaw, roll))
    blueprints = world.get_blueprint_library()
    ego_bp = blueprints.find(packet["ego_blueprint_id"])
    pedestrian_bp = blueprints.find(packet["pedestrian_blueprint_id"])
    if not ego_bp.id.startswith("vehicle.") or not pedestrian_bp.id.startswith("walker.pedestrian."):
        raise ValueError("Emergency vehicle or pedestrian blueprint classification mismatch")
    ego = world.try_spawn_actor(ego_bp, transform(packet["ego_transform"]))
    if ego is None:
        raise ValueError("Emergency vehicle spawn failed")
    pedestrian = None
    try:
        pedestrian = world.try_spawn_actor(pedestrian_bp, transform(packet["pedestrian_transform"]))
        if pedestrian is None:
            raise ValueError("Pedestrian spawn failed")
        ego.set_autopilot(False)
        return {"ego": ego, "pedestrian": pedestrian, "site_packet_sha256": hashlib.sha256(Path(packet_path).read_bytes()).hexdigest()}
    except Exception:
        if pedestrian is not None:
            pedestrian.destroy()
        ego.destroy()
        raise
