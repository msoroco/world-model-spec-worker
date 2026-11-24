"""Thirty-second shared crossing policy; branch switches affect requests only."""
from __future__ import annotations

import math

from geometry import INTERSECTION_X_M, EGO_LANE_Y_M, OTHER_LANE_X_M

RATE_HZ = 20
FRAMES = 600
SIREN_WINDOW = (100, 300)
LAMP_WINDOW = (80, 330)


def request(index, config):
    if type(index) is not int or not 0 <= index < FRAMES:
        raise ValueError("Exact frame index required")
    t = index / RATE_HZ
    ego_x = min(5 + 2 * t, 65)
    # The counterpart waits south of the junction while the emergency actor
    # approaches. Its presence is constructed; actual response remains unknown.
    other_y = min(-45 + 2 * t, -12) if t < 26 else -12 + 2 * (t - 26)
    siren_requested = bool(config.get("siren_requested")) and \
        SIREN_WINDOW[0] <= index < SIREN_WINDOW[1]
    lamps_requested = bool(config.get("warning_lamps_requested")) and \
        LAMP_WINDOW[0] <= index < LAMP_WINDOW[1]
    return {"frame_index": index, "time_s": t,
            "ego_target_xy_m": [ego_x, EGO_LANE_Y_M],
            "other_target_xy_m": [OTHER_LANE_X_M, other_y],
            "ego_speed_request_mps": 2.0 if ego_x < 65 else 0.0,
            "other_speed_request_mps": 2.0 if t < 16.5 or t >= 26 else 0.0,
            "siren_requested": siren_requested,
            "warning_lamps_requested": lamps_requested,
            "emergency_call_requested": bool(config.get("emergency_call_requested")),
            "immediate_pursuit_requested": bool(config.get("immediate_pursuit_requested")),
            "requests_are_not_observations": True}


def check(config):
    rows = [request(index, config) for index in range(FRAMES)]
    if len(rows) != 600 or any(not all(math.isfinite(value) for value in
                                      (*row["ego_target_xy_m"],
                                       *row["other_target_xy_m"]))
                               for row in rows):
        raise ValueError("Finite full-window control request required")
    if not (rows[0]["ego_target_xy_m"][0] < INTERSECTION_X_M and
            rows[-1]["ego_target_xy_m"][0] > INTERSECTION_X_M):
        raise ValueError("Emergency approach must cross constructed junction")
    if any(row["other_target_xy_m"][1] > -4 for row in rows):
        raise ValueError("Counterpart must remain outside crossing")
    if sum(row["siren_requested"] for row in rows) != \
            (200 if config.get("siren_requested") else 0):
        raise ValueError("Siren request window differs")
    if sum(row["warning_lamps_requested"] for row in rows) != \
            (250 if config.get("warning_lamps_requested") else 0):
        raise ValueError("Warning lamp request window differs")
    return {"frames": 600, "shared_motion_policy": True,
            "ego_crosses_authored_junction": True,
            "other_stays_south": True,
            "siren_request_frames": sum(row["siren_requested"] for row in rows),
            "lamp_request_frames": sum(row["warning_lamps_requested"] for row in rows),
            "physical_or_audio_success_claimed": False}
