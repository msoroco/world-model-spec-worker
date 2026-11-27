"""Original-frame physical observations for the conditional extreme-right duty.

The output retains measurements and unknown legal questions separately.
Neither engineering clearances nor speeds implement a legal predicate.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C323986__NRS-484B-627-1a__motor_vehicle_driver"


def _number(row: dict, key: str) -> float:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("original finite measurement required: " + key)
    return float(value)


def measure(path: str | Path) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    return measure_packet(json.loads(raw), {"path": str(path),
                                            "sha256": hashlib.sha256(raw).hexdigest()})


def measure_packet(packet: dict, source: dict) -> dict:
    if packet.get("assignment_id") != ASSIGNMENT or not packet.get("case_id", "").startswith(ASSIGNMENT + "__"):
        raise ValueError("wrong original assignment or exact case")
    if not packet.get("original_trace_id") or not packet.get("original_frame_map_sha256"):
        raise ValueError("original trace and frame-map binding required")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError("original frame history required")
    observed = []
    last_time = None
    for index, row in enumerate(frames):
        if row.get("frame") != index:
            raise ValueError("original frame index gap")
        t = _number(row, "time_s")
        if last_time is not None and not 0.049 <= t - last_time <= 0.051:
            raise ValueError("original 20 Hz time gap")
        last_time = t
        if not row.get("ego_actor_id") or not row.get("follower_actor_id"):
            raise ValueError("distinct original participant identities required")
        if row["ego_actor_id"] == row["follower_actor_id"]:
            raise ValueError("subject cannot be its own follower")
        if not row.get("ego_lane_id") or not row.get("follower_lane_id") or not row.get("opposite_lane_id"):
            raise ValueError("original lane directions missing")
        if type(row.get("one_lane_each_direction_readback")) is not bool:
            raise ValueError("original directional lane count required")
        if type(row.get("follower_immediately_behind_readback")) is not bool:
            raise ValueError("original immediate follower readback required")
        paved = _number(row, "paved_right_edge_m")
        highway = _number(row, "highway_right_edge_m")
        obstacle_left = _number(row, "obstruction_left_edge_m")
        obstacle_right = _number(row, "obstruction_right_edge_m")
        ego_right = _number(row, "ego_body_right_edge_m")
        ego_left = _number(row, "ego_body_left_edge_m")
        if not (ego_left < ego_right and obstacle_left < obstacle_right and paved <= highway):
            raise ValueError("original body, obstruction or road geometry inconsistent")
        ego_speed = _number(row, "ego_speed_mps")
        follower_speed = _number(row, "follower_speed_mps")
        gap = _number(row, "follower_along_route_body_gap_m")
        if min(ego_speed, follower_speed, gap) < 0:
            raise ValueError("original speed or body gap negative")
        obstruction_station = _number(row, "obstruction_station_m")
        ego_station = _number(row, "ego_station_m")
        follower_station = _number(row, "follower_station_m")
        if row["follower_immediately_behind_readback"] and (
                row["follower_lane_id"] != row["ego_lane_id"] or follower_station >= ego_station):
            raise ValueError("immediate follower conflicts with original lane or station")
        observed.append({
            "frame": index, "time_s": t,
            "one_lane_each_direction_readback": row["one_lane_each_direction_readback"],
            "immediately_behind_readback": row["follower_immediately_behind_readback"],
            "subject_speed_mps": ego_speed, "follower_speed_mps": follower_speed,
            "relative_closing_speed_mps": follower_speed - ego_speed,
            "follower_along_route_body_gap_m": gap,
            "paved_right_edge_m": paved, "highway_right_edge_m": highway,
            "ego_body_right_edge_m": ego_right,
            "ego_to_paved_right_edge_m": paved - ego_right,
            "ego_to_highway_right_edge_m": highway - ego_right,
            "obstruction_lateral_edges_m": [obstacle_left, obstacle_right],
            "obstruction_station_m": obstruction_station,
            "subject_station_m": ego_station,
            "obstruction_along_route_gap_m": obstruction_station - ego_station,
            "obstruction_to_paved_right_edge_m": paved - obstacle_right,
            "body_overlaps_obstruction_laterally": ego_right > obstacle_left and ego_left < obstacle_right,
        })
    return {
        "assignment_id": ASSIGNMENT, "case_id": packet["case_id"],
        "original_trace_id": packet["original_trace_id"],
        "original_frame_map_sha256": packet["original_frame_map_sha256"],
        "source": source, "observations": observed,
        "unresolved_judgments": [
            "Whether the subject speed impeded immediately following traffic",
            "Whether the width of the paved portion permitted driving to the extreme right side",
            "Whether and when NRS 484B.630 applied",
            "Whether the observed path satisfied the extreme-right duty",
        ],
        "review_limit": "A measured obstruction effect and follower speed response require original-source review; no clearance or speed threshold is adopted as law.",
    }
