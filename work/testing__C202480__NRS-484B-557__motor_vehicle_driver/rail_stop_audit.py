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
    for key in REQUIRED_SOURCES:
        binding = sources.get(key)
        if not isinstance(binding, dict):
            raise ValueError(f"missing source binding: {key}")
        relative = Path(binding.get("path", ""))
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError(f"unsafe source path: {key}")
        source_path = packet_path.parent / relative
        if not source_path.is_file():
            raise ValueError(f"missing source file: {key}")
        if hashlib.sha256(source_path.read_bytes()).hexdigest() != binding.get("sha256"):
            raise ValueError(f"source hash differs: {key}")
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
        gaps = []
        for origin, tangent in rail_lines:
            signed = [(x - origin[0]) * -tangent[1] + (y - origin[1]) * tangent[0] for x, y in corners]
            gaps.append((min(abs(v) for v in signed), min(signed), max(signed)))
        _, low, high = min(gaps, key=lambda item: item[0])
        rows.append({"frame": frame, "elapsed_s": elapsed, "speed_mps": speed,
                     "body_to_nearest_rail_min_ft": min(abs(low), abs(high)) * FEET_PER_METRE if low * high > 0 else 0.0,
                     "body_signed_range_ft": [low * FEET_PER_METRE, high * FEET_PER_METRE],
                     "source_frame": sample.get("source_frame")})
        if not sample.get("source_frame"):
            raise ValueError("sample lacks original source frame identity")
    first_rail_contact = next((r["frame"] for r in rows if r["body_to_nearest_rail_min_ft"] == 0.0), None)
    stopped = [r for r in rows if r["speed_mps"] == 0.0 and
               (first_rail_contact is None or r["frame"] < first_rail_contact)]
    if not stopped:
        return {"status": "measured", "complete_stop_observed": False, "stop_samples": [],
                "proceeding_observed": False, "due_care": "unresolved", "source_keys": list(REQUIRED_SOURCES)}
    first_stop = stopped[0]
    stop_frame = first_stop["frame"]
    preceding = [r for r in rows if r["frame"] < stop_frame]
    following = [r for r in rows if r["frame"] > stop_frame]
    proceeding = any(r["speed_mps"] > 0 for r in following)
    # Values near legal boundaries are measurements only; they are not labels.
    return {"status": "measured", "complete_stop_observed": True,
            "first_stop_frame": stop_frame, "first_stop_body_to_nearest_rail_min_ft": first_stop["body_to_nearest_rail_min_ft"],
            "first_stop_body_signed_range_ft": first_stop["body_signed_range_ft"],
            "stop_samples": [r["frame"] for r in stopped], "approach_samples": len(preceding),
            "proceeding_observed": proceeding, "departure_samples": len(following),
            "due_care": "requires independent scene-and-conflict review",
            "source_keys": list(REQUIRED_SOURCES)}
