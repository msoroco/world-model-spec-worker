"""Source-bound frame measurements for NRS 484D.215(1).

This measures Native geometry and lamp readback. Whether a physical beam reveals
people safely, projects glaring rays into eyes, or meets NRS 484D.210(2) stays
for original calibrated pixels and independent review.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

FEET_TO_METERS = 0.3048
LEGAL_DISTANCE_M = 500 * FEET_TO_METERS
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(root: Path, name: str, digest: str) -> Path:
    if "/" in name or "\\" in name or name in ("", ".", ".."):
        raise ValueError("source path must be a simple original filename")
    path = root / name
    if not path.is_file() or path.is_symlink() or _hash(path) != digest:
        raise ValueError("missing or changed original source: " + name)
    return path


def _rows(path: Path) -> list[dict]:
    rows = [json.loads(x) for x in path.read_text().splitlines() if x]
    if not rows or any(not isinstance(x, dict) for x in rows):
        raise ValueError("empty or malformed original frame rows")
    return rows


def _xyz(value: object, label: str) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3 or any(type(x) not in (float, int) or not math.isfinite(x) for x in value):
        raise ValueError("missing original 3D coordinate: " + label)
    return tuple(float(x) for x in value)


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.dist(a, b)


def _body_gap(a: tuple[float, float, float], b: tuple[float, float, float], ra: float, rb: float) -> float:
    if ra <= 0 or rb <= 0:
        raise ValueError("original body radii must be positive")
    return max(0.0, _distance(a, b) - ra - rb)


def measure(root: Path, source_hashes: dict[str, str], *, expected_frames: int = 900,
            case: dict | None = None) -> dict:
    """Validate original 20 Hz joins and report distance/beam observations.

    actor-state.jsonl requires original positions for ego, oncoming, a person
    ahead, and a separate target vehicle ahead. A source-reviewed site packet
    establishes highway polygon, nighttime applicability, contour and loading.
    Pixel reviews are separate and remain unresolved in this output.
    """
    root = Path(root)
    names = ("actor-state.jsonl", "camera-frame-map.jsonl", "site-packet.json")
    if set(source_hashes) != set(names):
        raise ValueError("all original source hashes required")
    paths = {name: _source(root, name, source_hashes[name]) for name in names}
    site = json.loads(paths["site-packet.json"].read_text())
    if (site.get("format") != "beam-road-site-v1" or
            site.get("source_reviewed") is not True or
            site.get("nevada_highway_public_access_reviewed") is not True or
            site.get("lighting_time_source_reviewed") is not True or
            site.get("lighting_time_qualifies") is not True or
            site.get("lamp_mounts_reviewed") is not True or
            site.get("driver_eye_sources_reviewed") is not True or
            site.get("contour_and_load_reviewed") is not True or
            not isinstance(site.get("source_refs"), list) or not site["source_refs"]):
        raise ValueError("reviewed qualifying highway, time, lamp, eye and contour source required")
    states = _rows(paths["actor-state.jsonl"])
    maps = _rows(paths["camera-frame-map.jsonl"])
    if len(states) != expected_frames or len(maps) != expected_frames or expected_frames < 2:
        raise ValueError("original 20 Hz duration or camera source count differs")
    base_frame = states[0].get("frame")
    if type(base_frame) is not int:
        raise ValueError("original frame ID required")
    first_t = states[0].get("time_s")
    if type(first_t) not in (int, float) or not math.isfinite(first_t):
        raise ValueError("original time required")
    ids: dict[str, object] = {}
    rows = []
    for index, (state, frame_map) in enumerate(zip(states, maps)):
        frame = base_frame + index
        if state.get("frame") != frame or frame_map.get("frame") != frame:
            raise ValueError("original frame identity is not contiguous")
        t = state.get("time_s")
        if type(t) not in (float, int) or not math.isfinite(t) or abs(t - (first_t + index / 20)) > .011:
            raise ValueError("original clock is not 20 Hz")
        for view in VIEWS:
            if frame_map.get(view + "_source_frame") != frame:
                raise ValueError("missing synchronized original camera frame: " + view)
        actors = state.get("actors")
        if not isinstance(actors, dict) or set(actors) != {"ego", "oncoming", "person", "target_vehicle"}:
            raise ValueError("all original participant sources required")
        centers = {}
        for role, actor in actors.items():
            if not isinstance(actor, dict) or type(actor.get("id")) not in (str, int):
                raise ValueError("original actor identity missing: " + role)
            if role in ids and ids[role] != actor["id"]:
                raise ValueError("original actor identity changed: " + role)
            ids[role] = actor["id"]
            centers[role] = _xyz(actor.get("center_m"), role + " center")
        ego = actors["ego"]
        incoming = actors["oncoming"]
        for role in ("ego", "oncoming"):
            actor = actors[role]
            if type(actor.get("speed_mps")) not in (float, int) or actor["speed_mps"] < 0 or not math.isfinite(actor["speed_mps"]):
                raise ValueError("original vehicle speed missing")
            if type(actor.get("body_radius_m")) not in (float, int) or actor["body_radius_m"] <= 0:
                raise ValueError("original vehicle body radius missing")
        if type(ego.get("lamp_state_bits")) is not int or type(ego.get("lamp_command_bits")) is not int:
            raise ValueError("original lamp command and readback required")
        if type(ego.get("on_traveled_highway_or_adjacent_shoulder")) is not bool or not ego["on_traveled_highway_or_adjacent_shoulder"]:
            raise ValueError("qualifying ego location not established")
        if type(incoming.get("opposing_route")) is not bool or not incoming["opposing_route"]:
            raise ValueError("oncoming route not established")
        eye_ego = _xyz(ego.get("driver_eye_m"), "ego eye")
        eye_incoming = _xyz(incoming.get("driver_eye_m"), "oncoming eye")
        body_gap = _body_gap(centers["ego"], centers["oncoming"], ego["body_radius_m"], incoming["body_radius_m"])
        eye_gap = _distance(eye_ego, eye_incoming)
        rows.append({"original_frame": frame, "time_s": round(float(t), 3),
                     "oncoming_body_gap_m": round(body_gap, 4),
                     "oncoming_eye_gap_m": round(eye_gap, 4),
                     "body_gap_within_500_ft": body_gap <= LEGAL_DISTANCE_M,
                     "eye_gap_within_500_ft": eye_gap <= LEGAL_DISTANCE_M,
                     "person_center_distance_m": round(_distance(centers["ego"], centers["person"]), 4),
                     "target_vehicle_center_distance_m": round(_distance(centers["ego"], centers["target_vehicle"]), 4),
                     "lamp_command_bits": ego["lamp_command_bits"],
                     "lamp_state_bits": ego["lamp_state_bits"]})
    if case is not None:
        if case.get("branch") == "general":
            if any(row["body_gap_within_500_ft"] or row["eye_gap_within_500_ft"] for row in rows):
                raise ValueError("general beam comparison entered oncoming 500-foot condition")
        elif case.get("branch") == "oncoming":
            if not any(row["body_gap_within_500_ft"] or row["eye_gap_within_500_ft"] for row in rows):
                raise ValueError("oncoming case never reached 500-foot condition")
        else:
            raise ValueError("unknown exact beam case branch")
    return {"format": "beam-road-original-measurement-v1", "frame_count": expected_frames,
            "first_original_frame": base_frame, "last_original_frame": base_frame + expected_frames - 1,
            "actor_ids": ids, "source_hashes": source_hashes, "rows": rows,
            "legal_distance_m": LEGAL_DISTANCE_M,
            "unresolved": ["Body and eye endpoints are both retained; legal 500-foot endpoint interpretation is unresolved.",
                           "Original calibrated pixels and reviewed eye ROI are required to assess actual glare.",
                           "Visibility at a safe distance has no numerical legal threshold in the supplied law.",
                           "CARLA low-beam bits alone do not prove the NRS 484D.210(2) lowermost distribution."]}
