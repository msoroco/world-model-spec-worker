"""Saved-only measurement of original bicycle, device, and officer history.

The input is an original Native packet sealed by its caller. Synthetic packets
exercise this checker but never establish a physical recording or legal result.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

FORMAT = "c111329-native-instruction-trace"
FRAME_COUNT = 900
STOP_SPEED_MPS = 0.2  # Engineering measurement tolerance, not a legal cutoff.
DWELL_FRAMES = 20      # One-second observable hold window, not a legal minimum.


def measure(path: Path, expected_sha256: str, case: dict, site: dict, site_sha256: str) -> dict:
    raw = path.read_bytes()
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ValueError("original instruction trace hash mismatch")
    packet = json.loads(raw)
    if packet.get("format") != FORMAT or packet.get("source_kind") != "original_native":
        raise ValueError("unverified original Native instruction packet")
    if packet.get("case_id") != case["case_id"] or packet.get("site_sha256") != site_sha256:
        raise ValueError("case or site source binding mismatch")
    rows = packet.get("samples")
    if not isinstance(rows, list) or len(rows) != FRAME_COUNT:
        raise ValueError("incomplete original 20 Hz instruction history")
    required = {"frame", "time_s", "bike_id", "bike_blueprint_id", "device_id",
                "device_state", "bike_front_xy", "bike_speed_mps", "officer_actor_id",
                "officer_authority_source", "officer_recipient_id", "officer_command"}
    x0, y0 = map(float, site["stop_line"][0])
    x1, y1 = map(float, site["stop_line"][1])
    if math.hypot(x1 - x0, y1 - y0) < 0.1:
        raise ValueError("degenerate original stop line")
    route_start = site["vehicle_route"][0]
    start_side = (x1 - x0) * (float(route_start[1]) - y0) - (y1 - y0) * (float(route_start[0]) - x0)
    if abs(start_side) < 0.1:
        raise ValueError("route starts on original stop line")
    sides = []
    first = rows[0]
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or not required.issubset(row):
            raise ValueError("missing original instruction sample source")
        if row["bike_id"] != first["bike_id"] or not row["bike_id"]:
            raise ValueError("bicycle identity changed")
        if row["bike_blueprint_id"] != site["bike_blueprint_id"] or row["device_id"] != site["device_id"]:
            raise ValueError("original participant or device identity mismatch")
        if row["device_state"] != case["device_instruction"]:
            raise ValueError("observed device instruction differs from case")
        if i:
            previous = rows[i - 1]
            if row["frame"] != previous["frame"] + 1 or not 0.04 <= row["time_s"] - previous["time_s"] <= 0.06:
                raise ValueError("original frame or 20 Hz clock discontinuity")
        speed = float(row["bike_speed_mps"])
        if not math.isfinite(speed) or speed < 0:
            raise ValueError("invalid original bicycle speed")
        xy = row["bike_front_xy"]
        if not isinstance(xy, list) or len(xy) != 2 or not all(math.isfinite(float(v)) for v in xy):
            raise ValueError("invalid original bicycle front position")
        side = (x1 - x0) * (float(xy[1]) - y0) - (y1 - y0) * (float(xy[0]) - x0)
        sides.append(side / abs(start_side))
        if case["officer_direction"] == "none":
            if row["officer_command"] != "none":
                raise ValueError("undeclared Police Officer command")
        else:
            if not row["officer_actor_id"] or row["officer_authority_source"] != site.get("police_authority_source"):
                raise ValueError("Police Officer identity or authority source missing")
            if row["officer_recipient_id"] != row["bike_id"]:
                raise ValueError("Police Officer command recipient mismatch")
            if row["officer_command"] not in {"none", case["officer_direction"]}:
                raise ValueError("Police Officer command differs from case")
    if sides[0] <= 0:
        raise ValueError("bicycle starts beyond governed stop line")
    crossing = next((i for i in range(1, len(sides)) if sides[i - 1] > 0 and sides[i] < 0), None)
    if case["operator_motion"] == "cross_stop_line":
        if crossing is None:
            raise ValueError("planned crossing absent from original history")
        event = crossing
    elif case["operator_motion"] == "hold_before_stop_line":
        if crossing is not None or min(sides) <= 0:
            raise ValueError("planned hold crossed original stop line")
        stationary = [i for i, row in enumerate(rows) if float(row["bike_speed_mps"]) <= STOP_SPEED_MPS and sides[i] > 0]
        if stationary[-DWELL_FRAMES:] != list(range(FRAME_COUNT - DWELL_FRAMES, FRAME_COUNT)):
            raise ValueError("planned hold lacks final observable dwell")
        event = FRAME_COUNT - DWELL_FRAMES
    else:
        raise ValueError("unknown planned bicycle movement")
    if case["officer_direction"] != "none":
        if any(row["officer_command"] != case["officer_direction"] for row in rows[max(0, event - DWELL_FRAMES): event + 1]):
            raise ValueError("Police Officer direction absent before response")
    return {
        "format": "c111329-saved-instruction-measurement",
        "source_kind": "original_native",
        "case_id": case["case_id"],
        "bike_id": first["bike_id"],
        "device_id": site["device_id"],
        "frame_count": FRAME_COUNT,
        "crossing_frame": rows[crossing]["frame"] if crossing is not None else None,
        "hold_window_frames": [rows[event]["frame"], rows[-1]["frame"]] if crossing is None else None,
        "device_state_at_response": rows[event]["device_state"],
        "officer_command_at_response": rows[event]["officer_command"],
        "source_hashes": {"site": site_sha256, "trace": actual_sha256},
        "legal_assessment": "unresolved",
    }
