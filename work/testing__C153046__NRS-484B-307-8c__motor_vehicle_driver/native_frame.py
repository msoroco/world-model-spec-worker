"""Capture original CARLA frame/body values without inferring legal outcomes."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from source_bound_scene import build as bind_scene


def _finite(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("nonfinite Native state")
    return value


def actor_state(actor) -> dict:
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    vertices = actor.bounding_box.get_world_vertices(transform)
    if len(vertices) < 4:
        raise ValueError("Native actor body lacks vertices")
    return {"actor_id": str(actor.id), "type_id": str(actor.type_id),
            "location_xyz_m": [_finite(getattr(transform.location, axis)) for axis in "xyz"],
            "heading_deg": _finite(transform.rotation.yaw),
            "velocity_xyz_mps": [_finite(getattr(velocity, axis)) for axis in "xyz"],
            "body_vertices_xyz_m": [[_finite(getattr(vertex, axis)) for axis in "xyz"]
                                     for vertex in vertices]}


def verify_live_site(world, packet_path: Path, suffix: str, signal_actor) -> dict:
    scene = bind_scene(packet_path, suffix)
    packet_path = Path(packet_path).resolve()
    packet = json.loads(packet_path.read_text())
    source = (packet_path.parent / packet["sources"]["opendrive"]["path"]).resolve()
    live = world.get_map().to_opendrive().encode("utf-8")
    if hashlib.sha256(live).hexdigest() != scene["source_hashes"]["opendrive"] or live != source.read_bytes():
        raise ValueError("live OpenDRIVE differs from retained site source")
    if str(signal_actor.id) != str(packet["signal"]["native_actor_id"]):
        raise ValueError("live signal actor differs from reviewed site proposal")
    return scene


def capture_tick(world, ego, signal_actor, pedestrians, traffic, *, expected_frame: int) -> dict:
    snapshot = world.get_snapshot()
    if snapshot.frame != expected_frame:
        raise ValueError("Native snapshot frame differs from tick")
    elapsed = _finite(snapshot.timestamp.elapsed_seconds)
    if elapsed < 0:
        raise ValueError("negative Native time")
    ego_state = actor_state(ego)
    ped_states = [actor_state(actor) for actor in pedestrians]
    traffic_states = [actor_state(actor) for actor in traffic]
    ids = [ego_state["actor_id"], *[item["actor_id"] for item in ped_states],
           *[item["actor_id"] for item in traffic_states]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate Native participant actor")
    return {"frame": expected_frame, "time_s": elapsed, "ego": ego_state,
            "signal_actor_id": str(signal_actor.id),
            "signal_state": str(signal_actor.get_state()),
            "pedestrians": ped_states, "other_traffic": traffic_states,
            "origin": "native_world_snapshot", "legal_judgment": "unresolved"}


def capture_frames(world, ego, signal_actor, pedestrians, traffic, *, count: int,
                   before_tick=None):
    if type(count) is not int or count <= 0:
        raise ValueError("positive original frame count required")
    last_time = None
    for index in range(count):
        if before_tick is not None:
            before_tick(index)
        frame = world.tick()
        sample = capture_tick(world, ego, signal_actor, pedestrians, traffic,
                              expected_frame=frame)
        if last_time is not None and sample["time_s"] <= last_time:
            raise ValueError("Native timestamps are not increasing")
        last_time = sample["time_s"]
        yield sample
