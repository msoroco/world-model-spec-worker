"""Source-gated construction and measurement for NRS 484B.203(1).

Coordinates are a local road frame: increasing s is ego travel, increasing y is
left of ego travel. This module never chooses a legal outcome or imports CARLA.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


VARIANTS = ("right_half", "wrong_side", "left_encroachment", "right_constrained")


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("finite numeric source value required")
    return float(value)


def load_sealed(path: Path, expected_sha256: str) -> dict:
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("source sha256 mismatch")
    return json.loads(raw)


def construct(map_packet: dict, variant: str) -> dict:
    """Return Native-lazy spawn/controller requests only for a verified site.

    An operator must bind this packet to live OpenDRIVE and recheck dimensions
    before actor spawn. A synthetic fixture cannot qualify a physical site.
    """
    if variant not in VARIANTS:
        raise ValueError("unknown case variant")
    if map_packet.get("source_kind") != "original_native_map_geometry":
        raise ValueError("original Native map packet required")
    if map_packet.get("layout") != "median_opening" or map_packet.get("public_highway") is not True:
        raise ValueError("median opening and highway source required")
    if map_packet.get("encounter_on_undivided_approach") is not True:
        raise ValueError("encounter must be on undivided approach")
    if map_packet.get("opposing_lane_directions") != [1, -1]:
        raise ValueError("two opposing directed lanes required")
    capacity = map_packet.get("traffic_line_capacity_each_direction")
    if capacity != [1, 1]:
        raise ValueError("source-confirmed single-line capacity required")
    lo, hi = map(_number, map_packet["paved_y_bounds_m"])
    if not lo < 0 < hi:
        raise ValueError("paved boundaries must bracket route axis")
    ego_half = _number(map_packet["ego_half_width_m"])
    other_half = _number(map_packet["other_half_width_m"])
    if min(ego_half, other_half) <= 0:
        raise ValueError("actor footprint invalid")
    corridor = map_packet.get("cross_sections")
    if not isinstance(corridor, list) or len(corridor) < 3:
        raise ValueError("source cross sections required")
    stations = [_number(row["s_m"]) for row in corridor]
    if stations != sorted(set(stations)) or max(b - a for a, b in zip(stations, stations[1:])) > 5:
        raise ValueError("cross sections must be ordered and no more than five metres apart")
    if stations[0] > -20 or stations[-1] < 20:
        raise ValueError("both approach directions need route coverage")
    for row in corridor:
        if row.get("source") != "native_map" or row.get("undivided") is not True:
            raise ValueError("each cross section needs Native undivided source")
        a, b = map(_number, row["paved_y_bounds_m"])
        if abs(a - lo) > 0.25 or abs(b - hi) > 0.25:
            raise ValueError("paved boundaries vary beyond reviewed route")
    centers = map_packet.get("verified_centers_y_m", {})
    ego_y = _number(centers[variant]["ego"])
    other_y = _number(centers[variant]["other"])
    if not (lo + ego_half < ego_y < hi - ego_half and lo + other_half < other_y < hi - other_half):
        raise ValueError("actor body exceeds paved portion")
    if abs(other_y - ego_y) <= ego_half + other_half:
        raise ValueError("opposing bodies do not clear one another")
    constraint = None
    if variant == "right_constrained":
        constraint = map_packet.get("physical_constraint")
        if (not isinstance(constraint, dict) or
                constraint.get("source_kind") != "original_native_map_geometry" or
                not constraint.get("source_id")):
            raise ValueError("right-constrained case requires source-recorded physical constraint")
        station_start, station_end = map(_number, constraint["station_range_m"])
        lateral_start, lateral_end = map(_number, constraint["lateral_range_m"])
        if not (station_start < 0 < station_end and lateral_start < lateral_end <= ego_y-ego_half):
            raise ValueError("right-side physical constraint does not bound encounter route")
        if ego_y-ego_half-lateral_end > 1.0:
            raise ValueError("right-side physical constraint is too remote from body route")
    return {
        "variant": variant,
        "coordinate_frame": "s_ego_forward_y_ego_left",
        "ego_route": [[s, ego_y] for s in stations],
        "other_route": [[s, other_y] for s in reversed(stations)],
        "ego_heading_sign": 1,
        "other_heading_sign": -1,
        "paved_y_bounds_m": [lo, hi],
        "single_line_capacity_source": map_packet.get("capacity_source"),
        "native_recheck_required": True,
        "physical_constraint_source": constraint,
    }


def spawn_native_pair(world, blueprint_library, map_packet: dict, variant: str, transform_factory):
    """Spawn the exact opposing pair after the source-gated site check.

    transform_factory converts the sealed packet's six-number poses to the
    simulator transform type. This keeps CARLA optional at import and CPU test.
    A failed second spawn destroys the first actor.
    """
    route = construct(map_packet, variant)
    spec = map_packet.get("native_spawn", {}).get(variant)
    if not isinstance(spec, dict):
        raise ValueError("source-bound Native spawn poses absent")
    created = []
    try:
        for role in ("ego", "other"):
            item = spec.get(role)
            if not isinstance(item, dict) or not isinstance(item.get("blueprint_id"), str):
                raise ValueError("actor blueprint source absent")
            pose = item.get("pose_xyz_ypr")
            if not isinstance(pose, list) or len(pose) != 6:
                raise ValueError("six-number source pose required")
            pose = [_number(v) for v in pose]
            if not item.get("source_id"):
                raise ValueError("spawn pose provenance absent")
            blueprint = blueprint_library.find(item["blueprint_id"])
            actor = world.try_spawn_actor(blueprint, transform_factory(pose))
            if actor is None:
                raise ValueError(f"{role} spawn failed")
            if not getattr(actor, "id", None) or not hasattr(actor, "get_transform"):
                raise ValueError("Native actor readback unavailable")
            readback = actor.get_transform()
            if readback is None:
                raise ValueError("Native spawn transform readback unavailable")
            created.append((role, actor))
        if created[0][1].id == created[1][1].id:
            raise ValueError("spawned actor identities are not distinct")
        return {
            "actors": {role: actor for role, actor in created},
            "actor_ids": [actor.id for _, actor in created],
            "route_request": route,
            "source_ids": [spec[role]["source_id"] for role in ("ego", "other")],
        }
    except Exception:
        for _, actor in reversed(created):
            actor.destroy()
        raise


def world_routes(map_packet: dict, variant: str) -> dict:
    """Project approved station/lateral routes into Native world coordinates."""
    route = construct(map_packet, variant)
    frame = map_packet.get("native_road_frame")
    if not isinstance(frame, dict) or not frame.get("source_id"):
        raise ValueError("source Native road frame absent")
    ox, oy, oz = map(_number, frame["origin_xyz_m"])
    fx, fy = map(_number, frame["forward_xy"])
    length = math.hypot(fx, fy)
    if abs(length - 1) > 1e-3:
        raise ValueError("Native road forward axis must be unit length")
    # Left of increasing station is the 90-degree counterclockwise normal.
    lx, ly = -fy, fx
    def project(points):
        return [[ox + s * fx + y * lx, oy + s * fy + y * ly, oz] for s, y in points]
    return {
        "ego_world_xyz_m": project(route["ego_route"]),
        "other_world_xyz_m": project(route["other_route"]),
        "frame_source_id": frame["source_id"],
        "native_waypoint_recheck_required": True,
    }


def measure(trace: dict) -> dict:
    """Measure a source-bound 20 Hz encounter from original actor readbacks."""
    if trace.get("source_kind") != "original_native_actor_history":
        raise ValueError("original Native actor history required")
    if trace.get("map_source_kind") != "original_native_map_geometry":
        raise ValueError("original Native map source required")
    if trace.get("public_highway") is not True or trace.get("encounter_on_undivided_approach") is not True:
        raise ValueError("site context missing")
    if trace.get("traffic_line_capacity_each_direction") != [1, 1]:
        raise ValueError("single-line capacity source missing")
    if not trace.get("capacity_source") or not trace.get("paved_boundary_source"):
        raise ValueError("map source identifiers missing")
    ego_id, other_id = trace.get("actor_ids", [None, None])
    if not ego_id or not other_id or ego_id == other_id:
        raise ValueError("distinct actor IDs required")
    samples = trace.get("samples")
    if not isinstance(samples, list) or len(samples) < 2:
        raise ValueError("continuous source samples required")
    contacts = []
    for i, row in enumerate(samples):
        if row.get("frame") != i or abs(_number(row["time_s"]) - i / 20) > 1e-4:
            raise ValueError("20 Hz frame or time continuity failed")
        if row.get("ego_id") != ego_id or row.get("other_id") != other_id:
            raise ValueError("actor identity changed")
        ego_speed = _number(row["ego_speed_s_mps"])
        other_speed = _number(row["other_speed_s_mps"])
        lo, hi = map(_number, row["paved_y_bounds_m"])
        if lo >= hi:
            raise ValueError("invalid paved boundary")
        es, ee = map(_number, row["ego_body_s_bounds_m"])
        os, oe = map(_number, row["other_body_s_bounds_m"])
        ey0, ey1 = map(_number, row["ego_body_y_bounds_m"])
        oy0, oy1 = map(_number, row["other_body_y_bounds_m"])
        if not (es <= ee and os <= oe and ey0 <= ey1 and oy0 <= oy1):
            raise ValueError("invalid measured body envelope")
        if max(es, os) <= min(ee, oe):
            if ego_speed <= 0 or other_speed >= 0:
                raise ValueError("opposing actual travel not established during passing")
            midpoint = (lo + hi) / 2
            contacts.append({
                "frame": i,
                "ego_right_of_other": ey1 <= oy0,
                "ego_north_edge_from_half_m": ey1 - midpoint,
                "other_south_edge_from_half_m": midpoint - oy0,
                "ego_body_paved": lo <= ey0 and ey1 <= hi,
                "other_body_paved": lo <= oy0 and oy1 <= hi,
                "paved_width_m": hi - lo,
            })
    if not contacts:
        raise ValueError("no measured passing interval")
    return {
        "passing_frames": [r["frame"] for r in contacts],
        "right_of_other_all": all(r["ego_right_of_other"] for r in contacts),
        "ego_north_edge_from_half_max_m": max(r["ego_north_edge_from_half_m"] for r in contacts),
        "other_south_edge_from_half_max_m": max(r["other_south_edge_from_half_m"] for r in contacts),
        "both_bodies_on_pavement_all": all(r["ego_body_paved"] and r["other_body_paved"] for r in contacts),
        "paved_width_range_m": [min(r["paved_width_m"] for r in contacts), max(r["paved_width_m"] for r in contacts)],
        "legal_judgment": "unresolved",
    }


def finalize_sealed(trace_path: Path, expected_sha256: str, output_path: Path) -> dict:
    """Write measured facts only after hashing the retained original trace."""
    trace = load_sealed(trace_path, expected_sha256)
    facts = measure(trace)
    document = {
        "source_path": str(trace_path),
        "source_sha256": expected_sha256,
        "measurement": facts,
        "physical_acceptance": "pending",
        "legal_judgment": "unresolved",
    }
    output_path = Path(output_path)
    if output_path.exists():
        raise FileExistsError(output_path)
    output_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return document


def audit_comparison(a: dict, b: dict, deliberate: str) -> None:
    """Reject missing source, nonmatching scene, or an unvaried intended factor."""
    required = ("source_kind", "map_sha256", "camera_profile", "duration_s", "actor_blueprints",
                "traffic_line_capacity_each_direction", "paved_boundary_source", "passing_frames", "measurements")
    if any(key not in row for row in (a, b) for key in required):
        raise ValueError("comparison source or measurement absent")
    if a["source_kind"] != b["source_kind"] or a["source_kind"] != "original_native_actor_history":
        raise ValueError("original source absent")
    fixed = required[1:7]
    if any(a[key] != b[key] for key in fixed):
        raise ValueError("comparison fixed condition changed")
    if not a["passing_frames"] or not b["passing_frames"]:
        raise ValueError("passing interval absent")
    if deliberate not in ("right_of_other_all", "ego_north_edge_from_half_max_m"):
        raise ValueError("unknown comparison factor")
    if a["measurements"][deliberate] == b["measurements"][deliberate]:
        raise ValueError("intended factor was not observed to differ")
