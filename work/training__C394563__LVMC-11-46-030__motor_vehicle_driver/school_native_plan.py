"""Exact 600-frame school-warning motion requests for prospective Native capture.

These are controller targets. The source meter must use observed poses, speeds,
warning actors, children, and release, not these requested values.
"""

from __future__ import annotations

import math

from school_warning_scene import CASES, FEET_PER_METRE, controller_command, scene_request, validate_request


FRAMES = 600
STOP_FRAME = 120
RELEASE_FRAME = 250
ARRIVAL_FRAME = 400
START_X_M = -65.0
END_X_M = 20.0


def plan(suffix):
    if suffix not in CASES:
        raise ValueError("Unknown exact school-warning case")
    request = scene_request(suffix)
    validate_request(request)
    stop_x = request["vehicle"]["requested_stop_center_x_m"]
    rows = []
    for index in range(FRAMES):
        if index < STOP_FRAME:
            target = START_X_M + (stop_x - START_X_M) * index / STOP_FRAME
            phase = "approach_stop"
        elif index < RELEASE_FRAME:
            target = stop_x
            phase = "hold_for_observed_release"
        elif index < ARRIVAL_FRAME:
            target = stop_x + (END_X_M - stop_x) * (index - RELEASE_FRAME) / (ARRIVAL_FRAME - RELEASE_FRAME)
            phase = "release_request_pending_source_review"
        else:
            target = END_X_M
            phase = "end_hold"
        rows.append({"frame": index, "time_s": index / 20,
                     "target_center_x_m": target, "target_y_m": -1.75,
                     "phase": phase,
                     "requested_warning_active": index < RELEASE_FRAME,
                     "requested_child_about_to_cross": index < RELEASE_FRAME,
                     "requested_signal_release": index == RELEASE_FRAME})
    return rows


def check_pair():
    first, second = plan("probe_1"), plan("probe_2")
    if len(first) != FRAMES or len(second) != FRAMES:
        raise ValueError("Exact 30-second request missing")
    if first[0]["target_center_x_m"] != START_X_M or second[0]["target_center_x_m"] != START_X_M:
        raise ValueError("Shared approach start differs")
    fixed = ("frame", "time_s", "target_y_m", "phase", "requested_warning_active",
             "requested_child_about_to_cross", "requested_signal_release")
    for index, (left, right) in enumerate(zip(first, second)):
        if any(left[key] != right[key] for key in fixed):
            raise ValueError("Fixed request policy differs at " + str(index))
        if not all(math.isfinite(item["target_center_x_m"]) for item in (left, right)):
            raise ValueError("Nonfinite Native target")
    for suffix, rows in (("probe_1", first), ("probe_2", second)):
        target = -CASES[suffix] / FEET_PER_METRE
        if any(abs(rows[index]["target_center_x_m"] - target) > 1e-9
               for index in range(STOP_FRAME, RELEASE_FRAME)):
            raise ValueError("Hold position differs")
    return {"case_suffixes": ["probe_1", "probe_2"],
            "frames": FRAMES, "rate_hz": 20,
            "hold_interval": [STOP_FRAME, RELEASE_FRAME],
            "requested_stop_center_ft": dict(CASES),
            "only_variable": "requested_stop_center_station",
            "physical_completion": None, "legal_outcome": None}


def command_for_observation(suffix, frame, observed_center_x_m, observed_speed_mps,
                            warning_active, observed_release):
    """Use observed release, never the request row, to authorize departure."""
    if frame >= RELEASE_FRAME and observed_release is None:
        stop_x = -CASES[suffix] / FEET_PER_METRE
        if observed_center_x_m >= stop_x - 1.0:
            return {"phase": "hold_pending_original_release", "throttle": 0.0,
                    "brake": 1.0, "steer": 0.0}
    return controller_command(suffix, frame, observed_center_x_m,
                              observed_speed_mps, warning_active, observed_release)


class SchoolController:
    """Stateful controller whose release latch requires an earlier observed stop."""

    def __init__(self, suffix):
        if suffix not in CASES:
            raise ValueError("Unknown exact school-warning case")
        self.suffix = suffix
        self.stopped_under_warning = False
        self.released_after_stop = False

    def step(self, frame, observed_center_x_m, observed_speed_mps,
             warning_active, observed_release):
        target = -CASES[self.suffix] / FEET_PER_METRE
        if (warning_active is True and observed_speed_mps <= 0.10 and
                abs(observed_center_x_m - target) <= 2.0):
            self.stopped_under_warning = True
        if observed_release is not None and self.stopped_under_warning:
            self.released_after_stop = True
        release = observed_release if self.released_after_stop else None
        command = command_for_observation(self.suffix, frame, observed_center_x_m,
                                          observed_speed_mps, warning_active, release)
        if not self.stopped_under_warning and command["phase"] == "released":
            raise ValueError("Controller released without observed prior stop")
        return command
