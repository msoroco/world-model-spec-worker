"""Saved Native packet audit for NRS 484B.557; no legal verdict is emitted.

Distances are reported for every sampled vehicle corner. The statute does not
specify a vehicle reference point, so the audit never selects one for it.
"""
from __future__ import annotations

import math
import hashlib
import json
from pathlib import Path
from typing import Any

FPS = 20
FEET_PER_METRE = 3.280839895013123
REQUIRED_SOURCES = (
    "native_crossing_geometry",
    "native_authority_record",
    "native_stop_device",
    "native_ego_kinematics",
    "native_ego_footprint",
)


def audit_saved_file(packet_path: Path) -> dict[str, Any]:
    """Verify every original source byte before interpreting a saved packet."""
    packet_path = Path(packet_path)
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    sources = packet.get("sources")
    if not isinstance(sources, dict):
        raise ValueError("sources must bind the original capture files")
    paths = {}
    for key in REQUIRED_SOURCES:
        binding = sources.get(key)
        if not isinstance(binding, dict):
            raise ValueError(f"missing source binding: {key}")
        relative = Path(binding.get("path", ""))
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError(f"unsafe source path: {key}")
        paths[key] = relative
    if packet.get("conflict_actor_present") is True:
        binding = sources.get("native_conflict_history")
        if not isinstance(binding, dict):
            raise ValueError("missing original crossing-conflict history")
        relative = Path(binding.get("path", ""))
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("unsafe crossing-conflict history path")
        paths["native_conflict_history"] = relative
    elif sources.get("native_conflict_history") is not None:
        raise ValueError("unselected crossing-conflict history")
    original = {}
    for key, relative in paths.items():
        binding = sources[key]
        source_path = (packet_path.parent / relative).resolve()
        if not source_path.is_relative_to(packet_path.parent.resolve()):
            raise ValueError(f"unsafe source path: {key}")
        if not source_path.is_file():
            raise ValueError(f"missing source file: {key}")
        data = source_path.read_bytes()
        if hashlib.sha256(data).hexdigest() != binding.get("sha256"):
            raise ValueError(f"source hash differs: {key}")
        try:
            original[key] = json.loads(data)
        except (ValueError, UnicodeError) as error:
            raise ValueError(f"original source is not structured: {key}") from error
    geometry = original["native_crossing_geometry"]
    authority = original["native_authority_record"]
    device = original["native_stop_device"]
    motion = original["native_ego_kinematics"]
    footprint = original["native_ego_footprint"]
    if not isinstance(geometry, dict) or packet.get("nearest_track_rails") != geometry.get("nearest_track_rails"):
        raise ValueError("packet rail geometry differs from original source")
    context = packet.get("context")
    if not isinstance(context, dict) or not isinstance(authority, dict) or not isinstance(device, dict):
        raise ValueError("original authority and device source missing")
    for field in ("crossing_type", "designation_authority", "dot_approval_source"):
        if field in context or field in authority:
            if context.get(field) != authority.get(field):
                raise ValueError("packet crossing authority differs from original source")
    for field in ("device_type", "device_governs"):
        if context.get(field) != device.get(field):
            raise ValueError("packet stop device differs from original source")
    if not isinstance(motion, list) or not isinstance(footprint, list):
        raise ValueError("original motion and footprint histories missing")
    samples = packet.get("samples")
    if not isinstance(samples, list) or len(samples) != len(motion) or len(samples) != len(footprint):
        raise ValueError("packet samples differ from original histories")
    for sample, movement, body in zip(samples, motion, footprint):
        if (not isinstance(movement, dict) or not isinstance(body, dict) or
                any(sample.get(key) != movement.get(key) for key in
                    ("frame", "source_frame", "elapsed_s", "speed_mps")) or
                any(sample.get(key) != body.get(key) for key in
                    ("frame", "source_frame", "body_corners_xy_m"))):
            raise ValueError("packet sample differs from original motion or footprint")
    if packet.get("conflict_actor_present") is True:
        conflict = original["native_conflict_history"]
        if not isinstance(conflict, list) or len(conflict) != len(samples):
            raise ValueError("original crossing-conflict frame history incomplete")
        for sample, actor in zip(samples, conflict):
            if (not isinstance(actor, dict) or actor.get("frame") != sample.get("frame") or
                    actor.get("source_frame") != sample.get("source_frame")):
                raise ValueError("original crossing-conflict frame join differs")
        if packet.get("conflict_samples") not in (None, conflict):
            raise ValueError("packet crossing-conflict samples differ from original")
        packet["conflict_samples"] = conflict
    return audit_saved_packet(packet)


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{name} must be numeric")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _point(value: Any, name: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{name} must have two coordinates")
    return (_finite_number(value[0], name), _finite_number(value[1], name))


def audit_saved_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Require original sampled geometry, authority, sign and complete motion.

    Each sample carries four world-space body corners, speed and original frame.
    The nearest rail is chosen from actual track lines by body-to-line gap. The
    stop interval requires a zero-speed sample before the first rail crossing;
    no arbitrary minimum stopping duration is inserted.
    """
    if not isinstance(packet, dict):
        raise ValueError("packet must be an object")
    sources = packet.get("sources")
    if not isinstance(sources, dict):
        raise ValueError("sources must bind the original capture files")
    for key in REQUIRED_SOURCES:
        item = sources.get(key)
        if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
            raise ValueError(f"missing source binding: {key}")
    context = packet.get("context")
    if not isinstance(context, dict):
        raise ValueError("missing crossing context")
    if context.get("crossing_type") != "highway_railroad_grade":
        raise ValueError("highway railroad grade crossing unestablished")
    if context.get("designation_authority") not in {"state_dot", "local_with_dot_approval"}:
        raise ValueError("crossing designation authority unestablished")
    if context.get("designation_authority") == "local_with_dot_approval" and not context.get("dot_approval_source"):
        raise ValueError("local designation lacks DOT approval source")
    if context.get("device_type") != "official_stop_sign" or context.get("device_governs") != "railroad_approach":
        raise ValueError("official stop sign governance unestablished")
    if context.get("actor") != "motor_vehicle_driver":
        raise ValueError("driver identity unestablished")
    tracks = packet.get("nearest_track_rails")
    if not isinstance(tracks, list) or not tracks:
        raise ValueError("nearest-track rail geometry missing")
    rail_lines = []
    for i, line in enumerate(tracks):
        a = _point(line.get("a"), f"rail {i} a")
        b = _point(line.get("b"), f"rail {i} b")
        dx, dy = b[0] - a[0], b[1] - a[1]
        norm = math.hypot(dx, dy)
        if norm <= 0:
            raise ValueError("rail line has zero length")
        rail_lines.append((a, (dx / norm, dy / norm)))
    samples = packet.get("samples")
    if not isinstance(samples, list) or len(samples) < 2:
        raise ValueError("complete sampled approach and departure required")
    rows = []
    prior_frame = None
    first_source_frame = None
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("sample must be an object")
        frame = sample.get("frame")
        if isinstance(frame, bool) or not isinstance(frame, int) or frame < 0:
            raise ValueError("invalid original frame")
        if prior_frame is not None and frame != prior_frame + 1:
            raise ValueError("original 20 Hz frame history has a gap")
        prior_frame = frame
        elapsed = _finite_number(sample.get("elapsed_s"), "elapsed_s")
        if abs(elapsed - frame / FPS) > 0.001:
            raise ValueError("elapsed time does not match 20 Hz original frames")
        speed = _finite_number(sample.get("speed_mps"), "speed_mps")
        if speed < 0:
            raise ValueError("negative speed")
        corners = sample.get("body_corners_xy_m")
        if not isinstance(corners, list) or len(corners) != 4:
            raise ValueError("four original vehicle body corners required")
        corners = [_point(c, "body corner") for c in corners]
        source_frame = sample.get("source_frame")
        if type(source_frame) is not int or source_frame < 0:
            raise ValueError("sample lacks original source frame identity")
        if first_source_frame is None:
            first_source_frame = source_frame
        if source_frame != first_source_frame + len(rows):
            raise ValueError("original source frame history has a gap")
        gaps = []
        for origin, tangent in rail_lines:
            signed = [(x - origin[0]) * -tangent[1] + (y - origin[1]) * tangent[0] for x, y in corners]
            low, high = min(signed), max(signed)
            gap = 0.0 if low <= 0 <= high else min(abs(low), abs(high))
            gaps.append((gap, low, high))
        _, low, high = min(gaps, key=lambda item: item[0])
        rows.append({"frame": frame, "elapsed_s": elapsed, "speed_mps": speed,
                     "body_to_nearest_rail_min_ft": min(abs(low), abs(high)) * FEET_PER_METRE if low * high > 0 else 0.0,
                     "body_signed_range_ft": [low * FEET_PER_METRE, high * FEET_PER_METRE],
                     "source_frame": source_frame})
    conflict_present = packet.get("conflict_actor_present") is True
    if conflict_present and "native_conflict_history" not in sources:
        raise ValueError("original crossing-conflict source missing")
    conflict_samples = packet.get("conflict_samples")
    if conflict_present:
        if not isinstance(conflict_samples, list) or len(conflict_samples) != len(samples):
            raise ValueError("original crossing-conflict samples missing")
        for sample, actor in zip(samples, conflict_samples):
            if (actor.get("frame") != sample["frame"] or
                    actor.get("source_frame") != sample["source_frame"] or
                    len(actor.get("body_corners_xy_m", [])) != 4):
                raise ValueError("crossing-conflict body/frame history differs")
            if _finite_number(actor.get("speed_mps"), "crossing-conflict speed") < 0:
                raise ValueError("negative crossing-conflict speed")
            for corner in actor["body_corners_xy_m"]:
                _point(corner, "crossing-conflict body corner")
    first_rail_contact = next((r["frame"] for r in rows if r["body_to_nearest_rail_min_ft"] == 0.0), None)
    first_approach_frame = next((r["frame"] for r in rows if r["speed_mps"] > 0.0), None)
    stopped = [r for r in rows if r["speed_mps"] == 0.0 and
               first_approach_frame is not None and r["frame"] > first_approach_frame and
               (first_rail_contact is None or r["frame"] < first_rail_contact)]
    if not stopped:
        return {"status": "measured", "complete_stop_observed": False, "stop_samples": [],
                "first_source_frame": first_source_frame,
                "last_source_frame": first_source_frame + len(rows) - 1,
                "proceeding_observed": False, "due_care": "unresolved",
                "conflict_actor_present": conflict_present,
                "source_keys": list(REQUIRED_SOURCES) + (["native_conflict_history"] if conflict_present else [])}
    first_stop = stopped[0]
    stop_frame = first_stop["frame"]
    preceding = [r for r in rows if r["frame"] < stop_frame]
    following = [r for r in rows if r["frame"] > stop_frame]
    proceeding = any(r["speed_mps"] > 0 for r in following)
    separation = None
    if conflict_present and following:
        def rectangle_gap(a, b):
            gaps = []
            for axis in (0, 1):
                low_a, high_a = min(p[axis] for p in a), max(p[axis] for p in a)
                low_b, high_b = min(p[axis] for p in b), max(p[axis] for p in b)
                gaps.append(max(low_a - high_b, low_b - high_a, 0.0))
            return math.hypot(*gaps)
        separation = min(rectangle_gap(samples[i]["body_corners_xy_m"],
                                       conflict_samples[i]["body_corners_xy_m"])
                         for i in range(len(rows)) if rows[i]["frame"] > stop_frame)
    # Values near legal boundaries are measurements only; they are not labels.
    return {"status": "measured", "complete_stop_observed": True,
            "first_source_frame": first_source_frame,
            "last_source_frame": first_source_frame + len(rows) - 1,
            "first_stop_frame": stop_frame, "first_stop_body_to_nearest_rail_min_ft": first_stop["body_to_nearest_rail_min_ft"],
            "first_stop_body_signed_range_ft": first_stop["body_signed_range_ft"],
            "stop_samples": [r["frame"] for r in stopped], "approach_samples": len(preceding),
            "proceeding_observed": proceeding, "departure_samples": len(following),
            "conflict_actor_present": conflict_present,
            "minimum_departure_conflict_body_separation_m": separation,
            "due_care": "requires independent scene-and-conflict review",
            "source_keys": list(REQUIRED_SOURCES) + (["native_conflict_history"] if conflict_present else [])}
