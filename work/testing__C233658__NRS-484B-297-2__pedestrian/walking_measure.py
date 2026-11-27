"""Measure original walking-side, facing and approach histories without a verdict."""
from __future__ import annotations

from math import hypot, isfinite


def _unit(pair: list[float]) -> tuple[float, float]:
    if len(pair) != 2 or not all(isinstance(x, (int, float)) and isfinite(x) for x in pair):
        raise ValueError("original direction vector missing")
    length = hypot(*pair)
    if length < 1e-6:
        raise ValueError("original direction vector is zero")
    return pair[0] / length, pair[1] / length


def measure(packet: dict) -> dict:
    site = packet.get("site", {})
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError("original walking history missing")
    if site.get("reviewed_public_highway") is not True or site.get("reviewed_sidewalk_absent") is not True or site.get("reviewed_subsection_6_inapplicable") is not True:
        raise ValueError("original site qualifications unresolved")
    center = site.get("centerline_xy_m")
    if not isinstance(center, list) or len(center) != 2 or any(not isinstance(point, list) or len(point) != 2 for point in center):
        raise ValueError("original highway centerline missing")
    cx, cy = center[0]
    rx, ry = _unit([center[1][0] - cx, center[1][1] - cy])
    side_history, facing_history, approach_history = [], [], []
    for index, row in enumerate(frames):
        pedestrian = row.get("pedestrian_xyz_m")
        vehicle = row.get("vehicle_xyz_m")
        if (not isinstance(pedestrian, list) or len(pedestrian) != 3 or
                not isinstance(vehicle, list) or len(vehicle) != 3 or
                not all(isinstance(x, (int, float)) and isfinite(x) for x in pedestrian + vehicle)):
            raise ValueError("original pedestrian/vehicle transform missing")
        px, py = _unit(row.get("pedestrian_forward_xy", []))
        vx, vy = _unit(row.get("vehicle_forward_xy", []))
        cross = rx * (pedestrian[1] - cy) - ry * (pedestrian[0] - cx)
        side_history.append("center_unknown" if cross == 0 else "center_left" if cross > 0 else "center_right")
        facing_history.append(px * vx + py * vy < 0)
        toward = (pedestrian[0] - vehicle[0]) * vx + (pedestrian[1] - vehicle[1]) * vy
        approach_history.append(toward > 0)
        if index and row.get("time_s", -1) <= frames[index - 1].get("time_s", -1):
            raise ValueError("original walking time not increasing")
    first, last = frames[0]["pedestrian_xyz_m"], frames[-1]["pedestrian_xyz_m"]
    progress = hypot(last[0] - first[0], last[1] - first[1])
    return {"frame_count": len(frames), "pedestrian_progress_m": progress,
            "pedestrian_side_history": side_history, "faces_traffic_history": facing_history,
            "vehicle_approaches_history": approach_history,
            "all_frames_facing": all(facing_history), "any_frame_vehicle_approaching": any(approach_history),
            "site_qualifications_reviewed": True}
