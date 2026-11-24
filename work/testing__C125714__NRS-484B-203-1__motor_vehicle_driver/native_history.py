"""Project original Native actor bodies into the surveyed opposing-road frame.

The supplied adapter owns world ticks, controls and actor cleanup. This module
seals observed motion only; requested routes never substitute for body readback.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from opposing_pass import _number, construct, load_sealed, measure, world_routes


def _project(vertices, origin, forward):
    if not isinstance(vertices, list) or len(vertices) != 8:
        raise ValueError("eight original body vertices required")
    left = (-forward[1], forward[0])
    stations, laterals = [], []
    for vertex in vertices:
        if not isinstance(vertex, (list, tuple)) or len(vertex) != 3:
            raise ValueError("original world vertex missing")
        x, y, z = map(_number, vertex)
        stations.append((x-origin[0])*forward[0] + (y-origin[1])*forward[1])
        laterals.append((x-origin[0])*left[0] + (y-origin[1])*left[1])
    return [min(stations), max(stations)], [min(laterals), max(laterals)]


def _paved(packet, ego_station, other_station):
    rows = packet["cross_sections"]
    midpoint = (ego_station + other_station) / 2
    row = min(rows, key=lambda item: abs(_number(item["s_m"]) - midpoint))
    if abs(_number(row["s_m"]) - midpoint) > 5:
        raise ValueError("original bodies outside surveyed cross sections")
    return list(map(_number, row["paved_y_bounds_m"]))


def capture(adapter, map_path, expected_map_sha256, variant, output,
            *, frames=900, diagnostic_fixture=False):
    """Write a once-only source-hashed trace for the exact variant."""
    if frames != 900 and not diagnostic_fixture:
        raise ValueError("production capture requires 900 original frames")
    if type(frames) is not int or frames < 2:
        raise ValueError("original frame count invalid")
    packet = load_sealed(map_path, expected_map_sha256)
    construct(packet, variant)
    world_routes(packet, variant)
    attestation = adapter.source_attestation()
    if not isinstance(attestation, dict) or not attestation.get("native_origin") \
            or attestation.get("map_sha256") != expected_map_sha256 \
            or not attestation.get("source_ref"):
        raise ValueError("original Native map attestation mismatch")
    frame = packet["native_road_frame"]
    origin = list(map(_number, frame["origin_xyz_m"]))
    forward = list(map(_number, frame["forward_xy"]))
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    rows, actor_ids = [], None
    first_time = previous_time = previous_frame = None
    for index in range(frames):
        sample = adapter.tick()
        if not isinstance(sample, dict):
            raise ValueError("original Native tick packet absent")
        native_frame = sample.get("native_frame")
        native_time = sample.get("native_elapsed_s")
        if type(native_frame) is not int or not isinstance(native_time, (int, float)) \
                or not math.isfinite(native_time):
            raise ValueError("original Native frame/time absent")
        if previous_frame is not None and (native_frame != previous_frame + 1 or
                abs(native_time - previous_time - .05) > .001):
            raise ValueError("original Native 20 Hz frame/time gap")
        if first_time is None:
            first_time = native_time
        if abs(native_time - first_time - index/20) > .001:
            raise ValueError("episode time diverged from original Native clock")
        previous_frame, previous_time = native_frame, native_time
        ego, other = sample.get("ego"), sample.get("other")
        if not isinstance(ego, dict) or not isinstance(other, dict):
            raise ValueError("two original actor samples required")
        ids = (ego.get("actor_id"), other.get("actor_id"))
        if not all(isinstance(v, (int, str)) and v for v in ids) or ids[0] == ids[1]:
            raise ValueError("distinct original actor IDs required")
        if actor_ids is None:
            actor_ids = ids
        if ids != actor_ids:
            raise ValueError("original actor identity drift")
        ego_s, ego_y = _project(ego.get("vertices_world_xyz_m"), origin, forward)
        other_s, other_y = _project(other.get("vertices_world_xyz_m"), origin, forward)
        ego_velocity = ego.get("velocity_world_xyz_mps")
        other_velocity = other.get("velocity_world_xyz_mps")
        if not isinstance(ego_velocity, list) or not isinstance(other_velocity, list) \
                or len(ego_velocity) != 3 or len(other_velocity) != 3:
            raise ValueError("original world velocity missing")
        ev = list(map(_number, ego_velocity))
        ov = list(map(_number, other_velocity))
        lo, hi = _paved(packet, sum(ego_s)/2, sum(other_s)/2)
        rows.append({"frame": index, "time_s": index/20,
                     "native_frame": native_frame, "native_elapsed_s": native_time,
                     "ego_id": ids[0], "other_id": ids[1],
                     "ego_speed_s_mps": ev[0]*forward[0]+ev[1]*forward[1],
                     "other_speed_s_mps": ov[0]*forward[0]+ov[1]*forward[1],
                     "paved_y_bounds_m": [lo, hi],
                     "ego_body_s_bounds_m": ego_s, "other_body_s_bounds_m": other_s,
                     "ego_body_y_bounds_m": ego_y, "other_body_y_bounds_m": other_y})
    trace = {"source_kind": "original_native_actor_history",
             "map_source_kind": packet["source_kind"],
             "map_sha256": expected_map_sha256, "variant": variant,
             "public_highway": packet["public_highway"],
             "encounter_on_undivided_approach": packet["encounter_on_undivided_approach"],
             "traffic_line_capacity_each_direction": packet["traffic_line_capacity_each_direction"],
             "capacity_source": packet["capacity_source"],
             "paved_boundary_source": packet["paved_boundary_source"],
             "actor_ids": list(actor_ids), "samples": rows,
             "native_source_attestation": attestation,
             "diagnostic_fixture": diagnostic_fixture,
             "physical_acceptance_claimed": False, "legal_judgment": "unresolved"}
    measure(trace)
    output.write_text(json.dumps(trace, sort_keys=True, separators=(",", ":")) + "\n",
                      encoding="utf-8")
    return {"path": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "frame_count": frames, "diagnostic_fixture": diagnostic_fixture}
