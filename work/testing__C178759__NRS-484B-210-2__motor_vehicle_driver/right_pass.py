"""Source-gated construction and measured right-side passing facts.

Coordinates use the Native road frame: station increases with ego travel and
positive lateral is left of ego. No measured quantity is a legal safety cutoff.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


VARIANTS = ("open_gap", "close_gap", "cross_traffic")


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("finite numeric source value required")
    return float(value)


def sealed_json(path: Path, sha256: str):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError("source sha256 mismatch")
    return json.loads(raw)


def construct(packet: dict, variant: str) -> dict:
    """Require surveyed Native lanes and full body clearance before requesting spawn."""
    if variant not in VARIANTS:
        raise ValueError("unknown right-pass variant")
    if packet.get("source_kind") != "original_native_map_geometry":
        raise ValueError("original Native map geometry required")
    if packet.get("layout") != "paved_road" or packet.get("right_lane_same_direction") is not True:
        raise ValueError("paved same-direction right lane required")
    if packet.get("pass_uses_shoulder") is not False:
        raise ValueError("shoulder use unresolved")
    if not packet.get("source_id") or not packet.get("paved_boundary_source"):
        raise ValueError("map provenance required")
    cross = packet.get("cross_sections")
    if not isinstance(cross, list) or len(cross) < 3:
        raise ValueError("surveyed corridor required")
    stations = [number(x["station_m"]) for x in cross]
    if stations != sorted(set(stations)) or stations[0] > -30 or stations[-1] < 30:
        raise ValueError("continuous approach and exit survey required")
    if max(b-a for a,b in zip(stations, stations[1:])) > 5:
        raise ValueError("cross-section sampling gap exceeds five metres")
    for row in cross:
        if row.get("source") != "native_map" or row.get("right_lane_same_direction") is not True:
            raise ValueError("each cross section must verify a right lane")
        lo, hi = map(number, row["paved_y_bounds_m"])
        left_y, right_y = map(number, row["lane_centers_y_m"])
        half = number(packet["max_actor_half_width_m"])
        if half <= 0 or not lo + half < right_y < left_y - 2*half < hi - half:
            raise ValueError("full vehicle footprints do not clear surveyed pavement")
    controls = packet.get("variant_controls", {}).get(variant)
    if not isinstance(controls, dict) or not controls.get("source_id"):
        raise ValueError("source-bound variant control absent")
    if variant == "cross_traffic" and not controls.get("cross_traffic_actor_pose_source"):
        raise ValueError("conflict actor construction source absent")
    target_speed = number(controls["target_speed_mps"])
    ego_speed = number(controls["ego_speed_mps"])
    if not 0 < target_speed < ego_speed:
        raise ValueError("overtaking speeds invalid")
    return {
        "variant": variant,
        "map_source_id": packet["source_id"],
        "route_station_m": stations,
        "ego_lane": "source_verified_right_same_direction_lane",
        "target_lane": "source_verified_left_same_direction_lane",
        "target_speed_mps": target_speed,
        "ego_speed_mps": ego_speed,
        "initial_longitudinal_body_gap_m": number(controls["initial_body_gap_m"]),
        "cross_traffic_actor_pose_source": controls.get("cross_traffic_actor_pose_source"),
        "native_readback_required": True,
    }


def spawn_native(world, blueprints, packet: dict, variant: str, transform_factory):
    """Instantiate source-pose actors lazily and clean up a partial spawn."""
    request = construct(packet, variant)
    spec = packet.get("native_spawn", {}).get(variant)
    if not isinstance(spec, dict):
        raise ValueError("Native spawn packet absent")
    roles = ("ego", "target", "conflict") if variant == "cross_traffic" else ("ego", "target")
    actors = {}
    try:
        for role in roles:
            item = spec.get(role)
            if not isinstance(item, dict) or not item.get("source_id"):
                raise ValueError("actor source pose absent")
            pose = item.get("pose_xyz_ypr")
            if not isinstance(pose, list) or len(pose) != 6:
                raise ValueError("source pose must contain six numbers")
            actor = world.try_spawn_actor(blueprints.find(item["blueprint_id"]),
                                          transform_factory([number(v) for v in pose]))
            if actor is None or not getattr(actor, "id", None) or actor.get_transform() is None:
                raise ValueError("Native actor spawn/readback failed")
            if actor.id in [a.id for a in actors.values()]:
                raise ValueError("duplicate Native actor identity")
            actors[role] = actor
        return {"actors": actors, "request": request}
    except Exception:
        for actor in reversed(list(actors.values())):
            actor.destroy()
        raise


def measure(history: dict) -> dict:
    """Measure actual approach, overlap and completion at 20 Hz from original bodies."""
    if history.get("source_kind") != "original_native_actor_history":
        raise ValueError("original Native actor history required")
    if history.get("map_source_kind") != "original_native_map_geometry":
        raise ValueError("original Native map source required")
    ids = history.get("actor_ids")
    if not isinstance(ids, list) or len(ids) < 2 or len(set(ids)) != len(ids):
        raise ValueError("distinct actor IDs required")
    if not history.get("map_sha256") or not history.get("camera_profile"):
        raise ValueError("map and camera provenance required")
    rows = history.get("samples")
    if not isinstance(rows, list) or len(rows) < 3:
        raise ValueError("continuous passing history required")
    phases = []
    gaps = []
    ttc = []
    lateral_clearance = []
    conflict_distances = []
    for i, row in enumerate(rows):
        if row.get("frame") != i or abs(number(row["time_s"])-i/20) > 0.001:
            raise ValueError("20 Hz original frame continuity failed")
        if row.get("actor_ids") != ids:
            raise ValueError("actor identities changed")
        es0, es1 = map(number, row["ego_body_s_bounds_m"])
        ts0, ts1 = map(number, row["target_body_s_bounds_m"])
        ey0, ey1 = map(number, row["ego_body_y_bounds_m"])
        ty0, ty1 = map(number, row["target_body_y_bounds_m"])
        lo, hi = map(number, row["paved_y_bounds_m"])
        ev, tv = map(number, (row["ego_speed_mps"], row["target_speed_mps"]))
        if not (es0 <= es1 and ts0 <= ts1 and ey0 <= ey1 and ty0 <= ty1 and lo <= ey0 and ey1 <= hi and lo <= ty0 and ty1 <= hi):
            raise ValueError("invalid body envelope or pavement containment")
        if not (ev > tv >= 0):
            raise ValueError("same-direction actual overtaking speeds absent")
        if len(ids) == 3:
            cs0, cs1 = map(number, row["conflict_body_s_bounds_m"])
            cy0, cy1 = map(number, row["conflict_body_y_bounds_m"])
            if cs0 > cs1 or cy0 > cy1:
                raise ValueError("invalid conflict actor body envelope")
            longitudinal = max(cs0-es1, es0-cs1, 0)
            lateral = max(cy0-ey1, ey0-cy1, 0)
            conflict_distances.append(math.hypot(longitudinal, lateral))
        if es1 < ts0:
            phase = "behind"
            gap = ts0-es1
            gaps.append(gap)
            ttc.append(gap/(ev-tv))
        elif es0 > ts1:
            phase = "ahead"
        else:
            phase = "alongside"
            lateral_clearance.append(ty0-ey1)
            if ey1 >= ty0:
                raise ValueError("measured ego is not clear on the right")
        phases.append(phase)
    if not ("behind" in phases and "alongside" in phases and "ahead" in phases):
        raise ValueError("whole right-side pass not observed")
    if phases.index("behind") > phases.index("alongside") or phases.index("alongside") > phases.index("ahead"):
        raise ValueError("passing phase order invalid")
    return {
        "passing_frames": [i for i,p in enumerate(phases) if p == "alongside"],
        "minimum_approach_body_gap_m": min(gaps),
        "minimum_approach_ttc_s": min(ttc),
        "minimum_lateral_body_clearance_m": min(lateral_clearance),
        "conflict_actor_present": len(ids) == 3,
        "minimum_conflict_body_distance_m": min(conflict_distances) if conflict_distances else None,
        "legal_safety_judgment": "unresolved",
    }


def finalize_sealed(history_path: Path, sha256: str, output_path: Path) -> dict:
    facts = measure(sealed_json(history_path, sha256))
    result = {"source_path": str(history_path), "source_sha256": sha256,
              "measurement": facts, "physical_acceptance": "pending",
              "legal_judgment": "unresolved"}
    output_path = Path(output_path)
    if output_path.exists():
        raise FileExistsError(output_path)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    return result


def audit_comparison(a: dict, b: dict, deliberate: str) -> None:
    """Check sealed-result context equality and actual measured difference."""
    fixed = ("map_sha256", "camera_profile", "duration_s", "primary_actor_blueprints", "paved_boundary_source")
    if any(k not in x for x in (a,b) for k in fixed+("measurement", "source_sha256")):
        raise ValueError("comparison source or measurement absent")
    if any(a[k] != b[k] for k in fixed):
        raise ValueError("comparison fixed condition changed")
    if deliberate not in ("minimum_approach_body_gap_m", "minimum_conflict_body_distance_m"):
        raise ValueError("undeclared comparison variable")
    if a["measurement"][deliberate] == b["measurement"][deliberate]:
        raise ValueError("intended difference not measured")
