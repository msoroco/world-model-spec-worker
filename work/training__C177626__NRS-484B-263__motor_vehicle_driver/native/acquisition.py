"""Validate Native source closure before yielding-gap measurements.

This module accepts original actor and camera readback only. A generated map
or controller request is not a measured highway designation or legal result.
"""

from __future__ import annotations

from hashlib import sha256
from math import hypot, isfinite
import json

from controlled_access_yield import FRAME_COUNT, FRAME_RATE
from multi_traffic_yield import assess_trace


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
HIGHWAY_IDS = {1, 2, 4}
RAMP_IDS = {3, 13}


def _actor(raw: dict, label: str) -> dict:
    if not isinstance(raw, dict):
        raise ValueError(f"missing {label} native readback")
    try:
        point = [float(v) for v in raw["center_xy_m"]]
        velocity = [float(v) for v in raw["velocity_xy_mps"]]
        radius = float(raw["radius_m"])
        road_id = int(raw["road_id"])
        lane_id = int(raw["lane_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid {label} native readback") from exc
    if len(point) != 2 or len(velocity) != 2 or not all(
        isfinite(v) for v in point + velocity + [radius]
    ) or radius <= 0 or lane_id != -1:
        raise ValueError(f"invalid {label} native geometry")
    return {"x_m": point[0], "y_m": point[1],
            "vx_mps": velocity[0], "vy_mps": velocity[1],
            "radius_m": radius, "road_id": road_id}


def bind_original(rows: list[dict], camera_rows: list[dict], context: dict,
                  policy: str) -> dict:
    """Require 600 joined original Native frames and four camera views."""
    if len(rows) != FRAME_COUNT or len(camera_rows) != FRAME_COUNT:
        raise ValueError("complete 600-frame native and camera sources required")
    if context.get("route_kind") != "entry" or context.get("map_source") != "native_opendrive_readback":
        raise ValueError("entry route and original map readback required")
    if not isinstance(context.get("map_sha256"), str) or len(context["map_sha256"]) != 64:
        raise ValueError("original map hash required")
    if context.get("controlled_access_designation_verified") is True:
        raise ValueError("authored map cannot establish legal designation")
    ids = context.get("approaching_vehicle_ids")
    if not isinstance(ids, list) or len(ids) < 2 or len(ids) != len(set(ids)):
        raise ValueError("two distinct inventoried highway vehicles required")
    network = {
        "route_kind": "entry", "highway_source": context["map_sha256"],
        "controlled_access_source": "designation_unresolved_original_map_geometry_only",
        "access_lane_id": "road3_or_13_lane-1",
        "highway_lane_id": "road1_or_2_or_4_lane-1",
        "conflict_point_source": context["map_sha256"] + ":junction100",
        "actor_inventory_source": context.get("actor_inventory_source"),
        "approaching_vehicle_ids": ids,
    }
    if not network["actor_inventory_source"]:
        raise ValueError("original actor inventory source required")
    measured = []
    saw_ramp = False
    saw_merge = False
    for i, (row, cameras) in enumerate(zip(rows, camera_rows)):
        if row.get("frame") != i or abs(row.get("time_s", -1) - i / FRAME_RATE) > 1e-6:
            raise ValueError("original native frame join failed")
        if cameras.get("frame") != row.get("native_frame") or set(cameras.get("views", {})) != set(VIEWS):
            raise ValueError("four exact original camera joins required")
        for view in VIEWS:
            if cameras["views"][view] != row["native_frame"]:
                raise ValueError("camera frame identity differs from native frame")
        ego = _actor(row.get("ego"), "ego")
        if ego["road_id"] not in RAMP_IDS | HIGHWAY_IDS:
            raise ValueError("ego left access/highway route")
        saw_ramp |= ego["road_id"] in RAMP_IDS
        saw_merge |= ego["road_id"] in {2, 4}
        traffic = row.get("traffic")
        if not isinstance(traffic, dict) or set(traffic) != set(ids):
            raise ValueError("original highway actor inventory differs")
        derived = {}
        for actor_id in ids:
            vehicle = _actor(traffic[actor_id], actor_id)
            if vehicle["road_id"] not in HIGHWAY_IDS:
                raise ValueError("inventoried vehicle left highway route")
            derived[actor_id] = {
                **{k: vehicle[k] for k in ("x_m", "y_m", "vx_mps", "vy_mps", "radius_m")},
                "distance_to_conflict_m": max(0.0, -vehicle["x_m"]),
                "on_highway": True,
                "approaching": vehicle["x_m"] < 0 and vehicle["vx_mps"] > 0,
            }
        measured.append({
            "frame": i, "time_s": row["time_s"],
            "ego": {**{k: ego[k] for k in ("x_m", "y_m", "vx_mps", "vy_mps", "radius_m")},
                    "distance_to_conflict_m": max(0.0, -ego["x_m"])},
            "traffic": derived,
            "ego_yielding": row.get("ego_yielding"),
        })
    if not saw_ramp or not saw_merge:
        raise ValueError("original ego entry traversal not observed")
    diagnostics = assess_trace(measured, network, policy)
    source_hash = sha256(json.dumps({"rows": rows, "cameras": camera_rows,
                                     "context": context}, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return {"original_source_sha256": source_hash,
            "camera_views": list(VIEWS), "frames": FRAME_COUNT,
            "map_source_sha256": context["map_sha256"],
            "controlled_access_designation_verified": False,
            "measurements": diagnostics}
