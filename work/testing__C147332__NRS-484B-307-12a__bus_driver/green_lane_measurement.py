"""Measure lane-specific green-arrow coverage from joined original sources.

The output reports observed signal and bus geometry. It makes no legal finding.
"""
from __future__ import annotations

import math
import re


HASH = re.compile(r"[0-9a-f]{64}\Z")


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(name + " must be finite")
    return float(value)


def source_hash(value, name):
    if not isinstance(value, str) or HASH.fullmatch(value) is None:
        raise ValueError(name + " source hash required")
    return value


def bounds(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("lane bounds required")
    low, high = (number(v, "lane bound") for v in value)
    if low >= high:
        raise ValueError("invalid lane bounds")
    return low, high


def corners(value):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("four original bus footprint corners required")
    result = []
    for point in value:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("invalid bus footprint corner")
        result.append((number(point[0], "body x"), number(point[1], "body y")))
    turns = []
    for i in range(4):
        a, b, c = (result[(i + j) % 4] for j in range(3))
        turns.append((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]))
    if not (all(x > 0 for x in turns) or all(x < 0 for x in turns)):
        raise ValueError("bus footprint must have ordered convex corners")
    return result


def measure(frames, *, motion_epsilon_m=0.05):
    """Require one highway and stable mapped overhead lane signals per attempt."""
    if not isinstance(frames, list) or len(frames) < 2:
        raise ValueError("at least two original joined frames required")
    epsilon = number(motion_epsilon_m, "motion epsilon")
    if epsilon < 0:
        raise ValueError("negative motion epsilon")
    highway = None
    official = None
    lanes = None
    last_frame = None
    last_time = None
    observations = []
    for sample in frames:
        frame = sample.get("frame")
        time = number(sample.get("elapsed_seconds"), "elapsed time")
        if isinstance(frame, bool) or not isinstance(frame, int) or frame < 0:
            raise ValueError("original frame identity required")
        if last_frame is not None and (frame != last_frame + 1 or time <= last_time):
            raise ValueError("contiguous original frame and time order required")
        last_frame, last_time = frame, time
        body, signal, camera = (sample.get(key) for key in ("body", "lane_signals", "camera_frame"))
        if not all(isinstance(value, dict) for value in (body, signal, camera)):
            raise ValueError("body, lane signals and camera source required")
        for name, value in (("body", body), ("lane signals", signal), ("camera", camera)):
            if value.get("frame") != frame or value.get("elapsed_seconds") != time:
                raise ValueError(name + " must join on original frame and time")
            source_hash(value.get("source_sha256"), name)
        if signal.get("faces_bus") is not True or signal.get("placement") != "over_individual_lanes":
            raise ValueError("bus-facing overhead lane signals required")
        h = signal.get("highway_id")
        if not isinstance(h, str) or not h:
            raise ValueError("highway identity required")
        o = source_hash(signal.get("official_device_source_sha256"), "official device")
        mapped = signal.get("lanes")
        if not isinstance(mapped, list) or len(mapped) < 2:
            raise ValueError("at least two same-direction mapped lanes required")
        current = {}
        for lane in mapped:
            if not isinstance(lane, dict):
                raise ValueError("mapped lane record required")
            ident = lane.get("lane_id")
            if not isinstance(ident, str) or not ident or ident in current:
                raise ValueError("unique lane identity required")
            if lane.get("direction") != "bus_direction":
                raise ValueError("same-direction lane mapping required")
            if lane.get("symbol") not in ("down_green_arrow", "other", "dark"):
                raise ValueError("observed lane signal symbol required")
            current[ident] = (bounds(lane.get("lateral_bounds_m")), lane["symbol"])
        intervals = sorted((v[0][0], v[0][1]) for v in current.values())
        if any(right[0] < left[1] for left, right in zip(intervals, intervals[1:])):
            raise ValueError("mapped lane bounds overlap")
        geometry = {key: value[0] for key, value in current.items()}
        if highway is not None and (h != highway or o != official or geometry != lanes):
            raise ValueError("highway, official device or lane geometry changed within attempt")
        highway, official, lanes = h, o, geometry
        body_points = corners(body.get("bus_footprint"))
        low, high = min(p[1] for p in body_points), max(p[1] for p in body_points)
        fully_in = sorted(key for key, (interval, _) in current.items()
                          if low >= interval[0] and high <= interval[1])
        under_green = [key for key in fully_in if current[key][1] == "down_green_arrow"]
        observations.append({"frame": frame, "elapsed_seconds": time,
                             "full_body_lane_ids": fully_in,
                             "green_covered_lane_ids": sorted(key for key, value in current.items()
                                                              if value[1] == "down_green_arrow"),
                             "permission_observed": bool(under_green),
                             "bus_center_x_m": sum(p[0] for p in body_points) / 4,
                             "body_source_sha256": body["source_sha256"],
                             "signal_source_sha256": signal["source_sha256"],
                             "camera_source_sha256": camera["source_sha256"]})
    moving = [now["frame"] for before, now in zip(observations, observations[1:])
              if abs(now["bus_center_x_m"] - before["bus_center_x_m"]) > epsilon]
    return {"highway_id": highway, "official_device_source_sha256": official,
            "mapped_lane_bounds_m": {key: list(value) for key, value in lanes.items()},
            "permission_observed_frames": [row["frame"] for row in observations
                                           if row["permission_observed"]],
            "bus_moving_frames": moving, "frame_observations": observations,
            "legal_judgment": "unresolved", "physical_acceptance_claimed": False}


def compare_green_indication(dark_frames, green_frames, selected_lane_id):
    """Require a controlled dark-to-green change over the same bus lane."""
    before, after = measure(dark_frames), measure(green_frames)
    if len(dark_frames) != len(green_frames):
        raise ValueError("comparison frame count changed")
    if (before["highway_id"] != after["highway_id"] or
            before["official_device_source_sha256"] != after["official_device_source_sha256"] or
            before["mapped_lane_bounds_m"] != after["mapped_lane_bounds_m"]):
        raise ValueError("comparison changed fixed highway, device or lane geometry")
    if selected_lane_id not in before["mapped_lane_bounds_m"]:
        raise ValueError("selected comparison lane is unmapped")
    for left, right in zip(dark_frames, green_frames):
        if left["frame"] != right["frame"] or left["elapsed_seconds"] != right["elapsed_seconds"]:
            raise ValueError("comparison changed original time window")
        if left["body"]["bus_footprint"] != right["body"]["bus_footprint"]:
            raise ValueError("comparison changed bus body motion")
        a = {lane["lane_id"]: lane for lane in left["lane_signals"]["lanes"]}
        b = {lane["lane_id"]: lane for lane in right["lane_signals"]["lanes"]}
        for ident in a:
            if ident != selected_lane_id and a[ident] != b[ident]:
                raise ValueError("comparison changed an unselected lane indication")
            if ident == selected_lane_id and (a[ident]["symbol"] != "dark" or
                                              b[ident]["symbol"] != "down_green_arrow"):
                raise ValueError("comparison lacks selected dark-to-green change")
    if before["permission_observed_frames"] or not after["permission_observed_frames"]:
        raise ValueError("comparison lacks measured permission difference")
    return {"selected_lane_id": selected_lane_id,
            "dark_permission_frames": before["permission_observed_frames"],
            "green_permission_frames": after["permission_observed_frames"],
            "bus_motion_held_fixed": True, "legal_judgment": "unresolved"}


def compare_permission_without_motion(driving_frames, standing_frames):
    """Check that a green indication remains while realized motion changes."""
    moving, still = measure(driving_frames), measure(standing_frames)
    if len(driving_frames) != len(standing_frames):
        raise ValueError("comparison frame count changed")
    if (moving["highway_id"] != still["highway_id"] or
            moving["official_device_source_sha256"] != still["official_device_source_sha256"] or
            moving["mapped_lane_bounds_m"] != still["mapped_lane_bounds_m"]):
        raise ValueError("comparison changed fixed highway, device or lane geometry")
    for left, right in zip(driving_frames, standing_frames):
        if left["frame"] != right["frame"] or left["elapsed_seconds"] != right["elapsed_seconds"]:
            raise ValueError("comparison changed original time window")
        if left["lane_signals"]["lanes"] != right["lane_signals"]["lanes"]:
            raise ValueError("comparison changed the green indications")
        if ([point[1] for point in left["body"]["bus_footprint"]] !=
                [point[1] for point in right["body"]["bus_footprint"]]):
            raise ValueError("comparison changed bus lane")
    if (not moving["bus_moving_frames"] or still["bus_moving_frames"] or
            not moving["permission_observed_frames"] or
            moving["permission_observed_frames"] != still["permission_observed_frames"]):
        raise ValueError("comparison lacks fixed permission and changed motion")
    return {"permission_frames": moving["permission_observed_frames"],
            "driving_frames": moving["bus_moving_frames"],
            "standing_motion_frames": still["bus_moving_frames"],
            "legal_judgment": "unresolved"}
