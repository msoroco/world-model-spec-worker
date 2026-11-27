"""Source-bound engineering measurement for NRS 484B.460.

This module measures angles and source continuity. It never classifies a halt
legally, applies an invented angle tolerance, or treats a planned value as an
observed one.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return value


def _unit(edge: list[object]) -> tuple[float, float]:
    if not isinstance(edge, list) or len(edge) != 2:
        raise ValueError("curb edge requires two original endpoints")
    points = []
    for point in edge:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("curb edge endpoint must be two coordinates")
        points.append((_finite(point[0], "curb x"), _finite(point[1], "curb y")))
    dx, dy = points[1][0] - points[0][0], points[1][1] - points[0][1]
    norm = math.hypot(dx, dy)
    if norm < 0.01:
        raise ValueError("curb edge is degenerate")
    return dx / norm, dy / norm


def _body_angle(yaw_deg: object, curb: tuple[float, float]) -> float:
    yaw = math.radians(_finite(yaw_deg, "body yaw"))
    dot = abs(math.cos(yaw) * curb[0] + math.sin(yaw) * curb[1])
    return math.degrees(math.acos(max(0.0, min(1.0, dot))))


def measure(packet: dict) -> dict:
    if not isinstance(packet, dict) or packet.get("source_kind") not in {"original_native", "diagnostic_native_shape"}:
        raise ValueError("original Native or explicit diagnostic source packet required")
    diagnostic = packet["source_kind"] == "diagnostic_native_shape"
    if diagnostic and packet.get("diagnostic_fixture") is not True:
        raise ValueError("diagnostic source must declare fixture provenance")
    for key in ("assignment_id", "case_id", "capture_source_sha256", "device_source_sha256", "frame_map_sha256"):
        value = packet.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"missing source binding: {key}")
    if packet["assignment_id"] != "testing__C377875__NRS-484B-460__motor_vehicle_driver":
        raise ValueError("assignment identity mismatch")
    if not packet["case_id"].startswith(packet["assignment_id"] + "__"):
        raise ValueError("case identity mismatch")
    device = packet.get("device")
    if not isinstance(device, dict) or device.get("official_status") != "reviewed_original":
        raise ValueError("reviewed original official-device status required")
    if device.get("governs_selected_space") is not True:
        raise ValueError("original device scope does not establish selected space")
    if not isinstance(device.get("content_review"), str) or not device["content_review"]:
        raise ValueError("original device content review required")
    indicated = _finite(device.get("indicated_angle_degrees"), "indicated angle")
    if not 0 <= indicated <= 90:
        raise ValueError("indicated angle outside geometric range")
    if packet.get("highway_source_review") != "reviewed_original":
        raise ValueError("original highway-context review required")
    curb = _unit(packet.get("curb_edge_xy"))
    rows = packet.get("frames")
    if not isinstance(rows, list) or not rows:
        raise ValueError("original frame rows required")
    expected = rows[0].get("frame") if isinstance(rows[0], dict) else None
    if not isinstance(expected, int) or isinstance(expected, bool):
        raise ValueError("invalid initial frame")
    angles = []
    halt_frames = []
    purpose = packet.get("halt_purpose_review")
    if not isinstance(purpose, dict) or purpose.get("status") != "reviewed_original":
        raise ValueError("original halt-purpose review required")
    for row in rows:
        if not isinstance(row, dict) or row.get("frame") != expected:
            raise ValueError("noncontiguous original frame map")
        expected += 1
        if row.get("halt_observed") is True:
            angles.append(_body_angle(row.get("body_yaw_degrees"), curb))
            halt_frames.append(row["frame"])
        elif row.get("halt_observed") is not False:
            raise ValueError("halt observation missing")
    if len(halt_frames) < 2:
        raise ValueError("at least two observed halt frames required")
    return {
        "format": "worker-angle-engineering-measurement",
        "assignment_id": packet["assignment_id"],
        "case_id": packet["case_id"],
        "source_bindings": {k: packet[k] for k in ("capture_source_sha256", "device_source_sha256", "frame_map_sha256")},
        "diagnostic_fixture": diagnostic,
        "indicated_angle_degrees": indicated,
        "halt_first_frame": halt_frames[0],
        "halt_last_frame": halt_frames[-1],
        "halt_frame_count": len(halt_frames),
        "body_to_curb_angle_min_degrees": min(angles),
        "body_to_curb_angle_max_degrees": max(angles),
        "body_to_curb_angle_mean_degrees": sum(angles) / len(angles),
        "mean_difference_from_indication_degrees": sum(angles) / len(angles) - indicated,
        "legal_classification": "unreviewed",
        "physical_original_review": "pending",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sha256(args.source) != args.source_sha256:
        raise ValueError("original source hash mismatch")
    result = measure(json.loads(args.source.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
