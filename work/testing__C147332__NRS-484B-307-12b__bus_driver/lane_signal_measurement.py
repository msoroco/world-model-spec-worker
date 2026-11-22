"""Measure bus entry and travel under a lane-specific red X from saved frames.

This module records geometry and source joins. It does not make a legal finding.
"""
from __future__ import annotations

import math
import re


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _corners(sample):
    corners = sample.get("bus_footprint")
    if not isinstance(corners, list) or len(corners) != 4:
        raise ValueError("four original bus footprint corners required")
    return [(_number(p[0], "footprint x"), _number(p[1], "footprint y")) for p in corners]


def measure(frames, *, motion_epsilon_m=0.05):
    """Join original body, signal and camera references on the same frame/time.

    The red lane is a lateral interval on the authored one-way road. The interval
    and bus polygon must be expressed in the same map coordinate system. An
    observed entry is a transition from no footprint overlap to overlap. Driving
    is longitudinal displacement while overlapping under red; epsilon is only
    a measurement noise tolerance, not a statutory allowance.
    """
    if not isinstance(frames, list) or len(frames) < 2:
        raise ValueError("at least two original joined frames required")
    epsilon = _number(motion_epsilon_m, "motion epsilon")
    if epsilon < 0:
        raise ValueError("negative motion epsilon")
    rows = []
    last_frame = -1
    last_time = -math.inf
    lane_identity = None
    lane_bounds = None
    official_source = None
    for sample in frames:
        frame = sample.get("frame")
        time = _number(sample.get("elapsed_seconds"), "elapsed time")
        if not isinstance(frame, int) or isinstance(frame, bool) or frame <= last_frame or time <= last_time:
            raise ValueError("original frame and time order required")
        last_frame, last_time = frame, time
        body = sample.get("body")
        signal = sample.get("lane_signal")
        camera = sample.get("camera_frame")
        if not isinstance(body, dict) or not isinstance(signal, dict) or not isinstance(camera, dict):
            raise ValueError("body, lane signal and camera source required at every frame")
        if any(obj.get("frame") != frame or obj.get("elapsed_seconds") != time
               for obj in (body, signal, camera)):
            raise ValueError("body, signal and camera must join on frame and time")
        if any(not isinstance(obj.get("source_sha256"), str) or
               not re.fullmatch(r"[0-9a-f]{64}", obj["source_sha256"])
               for obj in (body, signal, camera)):
            raise ValueError("original source hash required for every channel")
        if (signal.get("faces_bus") is not True or
                not isinstance(signal.get("official_device_source_sha256"), str) or
                not re.fullmatch(r"[0-9a-f]{64}", signal["official_device_source_sha256"])):
            raise ValueError("facing official lane-signal source required")
        if signal.get("symbol") not in ("red_x", "other"):
            raise ValueError("observed signal symbol required")
        lane = signal.get("governed_lane_id")
        if not isinstance(lane, str) or not lane:
            raise ValueError("governed lane identity required")
        if lane_identity is not None and lane != lane_identity:
            raise ValueError("governed lane changed within comparison")
        lane_identity = lane
        bounds = signal.get("lane_lateral_bounds_m")
        if not isinstance(bounds, list) or len(bounds) != 2:
            raise ValueError("original lane bounds required")
        low, high = (_number(v, "lane bound") for v in bounds)
        if low >= high:
            raise ValueError("invalid governed lane bounds")
        if lane_bounds is not None and (low, high) != lane_bounds:
            raise ValueError("governed lane bounds changed within comparison")
        lane_bounds = (low, high)
        packet_sha = signal["official_device_source_sha256"]
        if official_source is not None and packet_sha != official_source:
            raise ValueError("official device packet changed within comparison")
        official_source = packet_sha
        corners = _corners(body)
        min_y, max_y = min(p[1] for p in corners), max(p[1] for p in corners)
        overlaps = max_y > low and min_y < high
        center_x = sum(p[0] for p in corners) / 4
        rows.append({"frame": frame, "elapsed_seconds": time, "red": signal.get("symbol") == "red_x",
                     "overlaps_governed_lane": overlaps, "bus_center_x_m": center_x,
                     "signal_source_sha256": signal["source_sha256"],
                     "body_source_sha256": body["source_sha256"],
                     "camera_source_sha256": camera["source_sha256"]})
    entries = [row["frame"] for before, row in zip(rows, rows[1:])
               if row["red"] and row["overlaps_governed_lane"] and
               not before["overlaps_governed_lane"]]
    driving = [row["frame"] for before, row in zip(rows, rows[1:])
               if before["red"] and row["red"] and before["overlaps_governed_lane"] and
               row["overlaps_governed_lane"] and
               abs(row["bus_center_x_m"] - before["bus_center_x_m"]) > epsilon]
    return {"governed_lane_id": lane_identity, "governed_lane_bounds_m": list(lane_bounds),
            "official_device_source_sha256": official_source, "red_x_entry_frames": entries,
            "red_x_driving_frames": driving, "frame_observations": rows,
            "legal_judgment": "unresolved", "physical_acceptance_claimed": False}
