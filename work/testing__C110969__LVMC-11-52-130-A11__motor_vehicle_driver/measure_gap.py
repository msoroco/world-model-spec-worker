"""Read original Native pose samples for a proposed intersection halt.

This computes a physical measurement only. It makes no necessity or legal finding.
"""

import hashlib
import json
import math
from pathlib import Path

from intersection_geometry import Box, footprint, polygon_gap_to_boundary


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _inside_source(root, source, name):
    relative = Path(source["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(name + " path escapes saved acquisition")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(name + " missing or outside saved acquisition")
    if _sha(path) != source["sha256"]:
        raise ValueError(name + " missing or hash mismatch")
    return path


def measure(packet_path):
    packet_path = Path(packet_path)
    packet = json.loads(packet_path.read_text())
    map_path = _inside_source(packet_path.parent, packet["map_source"], "map_source")
    pose_path = _inside_source(packet_path.parent, packet["pose_source"], "pose_source")
    map_data = json.loads(map_path.read_text())
    if not map_data.get("map_id") or not map_data.get("geometry_provenance"):
        raise ValueError("Intersection map identity/provenance missing")
    bounds = map_data["intersection_boundary_local_m"]
    boundary = Box(bounds["west"], bounds["south"], bounds["east"], bounds["north"])
    length = float(packet["vehicle_length_m"])
    width = float(packet["vehicle_width_m"])
    frames = []
    with pose_path.open() as stream:
        for raw in stream:
            frame = json.loads(raw)
            frames.append(frame)
    if len(frames) != 900:
        raise ValueError("Need full 900-frame original trace")
    if [f["frame"] for f in frames] != list(range(900)):
        raise ValueError("Original frame sequence incomplete")
    if any(abs(f["time_s"] - f["frame"] / 20) > 1e-6 for f in frames):
        raise ValueError("Original time sequence is not 20 Hz")
    if any(f.get("actor_id") != packet["actor_id"] for f in frames):
        raise ValueError("Actor binding changed within original trace")
    halted = [f for f in frames if f.get("halt_state") is True and f.get("speed_mps", 1) <= 0.1]
    halt_runs = []
    current = []
    for frame in frames:
        if frame.get("halt_state") is True and frame.get("speed_mps", 1) <= 0.1:
            current.append(frame)
        elif current:
            halt_runs.append(current)
            current = []
    if current:
        halt_runs.append(current)
    complete_runs = [run for run in halt_runs if len(run) >= 40]
    if not complete_runs:
        raise ValueError("No contiguous two-second observed halt")
    halted = [frame for run in complete_runs for frame in run]
    if any(not all(math.isfinite(float(f[key])) for key in
                   ("x_m", "y_m", "heading_deg", "speed_mps")) for f in halted):
        raise ValueError("Nonfinite original halt sample")
    gaps = [polygon_gap_to_boundary(footprint(f["x_m"], f["y_m"],
                                                    f["heading_deg"], length, width), boundary)
            for f in halted]
    return {"map_id": map_data["map_id"], "actor_id": packet["actor_id"],
            "original_frame_count": 900, "halt_frame_count": len(halted),
            "halt_intervals": [{"first_frame": run[0]["frame"],
                                "last_frame": run[-1]["frame"]} for run in complete_runs],
            "minimum_halt_body_gap_m": min(gaps),
            "maximum_halt_body_gap_m": max(gaps),
            "map_sha256": packet["map_source"]["sha256"],
            "pose_sha256": packet["pose_source"]["sha256"],
            "limitations": ["Original samples do not establish the driver's purpose or legal necessity.",
                            "The source-bound intersection boundary still requires physical map review."]}
