"""Measure a source-joined aggressive-driving conduct envelope.

Inputs are retained original-frame motion and separately derived episode facts.
This module measures distance and event ordering; it makes no speeding,
passing-lawfulness, immediate-hazard, or offense decision.
"""

from __future__ import annotations

from math import hypot, isfinite

MILE_M = 1609.344


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("Missing finite " + label)
    return float(value)


def measure_sequence(frames, right_pass_episodes, speeding_frames, hazard_frames):
    """Return the event-enclosing traveled distance and raw episode ordering.

    `right_pass_episodes` must be source-derived records with start/end frame,
    target vehicle ID, pre/post longitudinal gaps, rightward separation, and
    off-pavement frame IDs. The latter are geometry measurements, not a legal
    verdict. Speeding and hazard frame IDs point to independent source reviews.
    """
    if not isinstance(frames, list) or len(frames) < 2:
        raise ValueError("At least two original motion frames required")
    index, traveled = {}, 0.0
    driver = frames[0].get("driver_id")
    if driver is None:
        raise ValueError("Original driver identity missing")
    previous = None
    for row in frames:
        frame = row.get("frame")
        if type(frame) is not int or frame in index:
            raise ValueError("Duplicate or invalid original frame")
        if row.get("driver_id") != driver:
            raise ValueError("Continuous period changed driver")
        time_s = _number(row.get("time_s"), "source time")
        x, y = (_number(row.get(key), key) for key in ("x_m", "y_m"))
        if previous is not None:
            if frame != previous["frame"] + 1 or time_s <= previous["time_s"]:
                raise ValueError("Original driving period is discontinuous")
            traveled += hypot(x - previous["x_m"], y - previous["y_m"])
        index[frame] = {"distance_m": traveled, "time_s": time_s}
        previous = {"frame": frame, "time_s": time_s, "x_m": x, "y_m": y}

    episodes = []
    for event in right_pass_episodes:
        start, end = event.get("start_frame"), event.get("end_frame")
        if type(start) is not int or type(end) is not int or start not in index or end not in index or start >= end:
            raise ValueError("Passing episode has no original-frame span")
        if not event.get("target_vehicle_id"):
            raise ValueError("Passing participant identity missing")
        before = _number(event.get("before_gap_m"), "pre-passing longitudinal gap")
        after = _number(event.get("after_gap_m"), "post-passing longitudinal gap")
        rightward = _number(event.get("rightward_separation_m"), "passing side")
        off_pavement = event.get("off_pavement_frames")
        if before >= 0 or after <= 0 or rightward <= 0:
            raise ValueError("Rightward order reversal is not source-supported")
        if (not isinstance(off_pavement, list) or not off_pavement
                or any(type(frame) is not int or frame not in index or
                       not start <= frame <= end for frame in off_pavement)):
            raise ValueError("Off-pavement source frames missing from episode")
        episodes.append({"start_frame": start, "end_frame": end,
                         "target_vehicle_id": event["target_vehicle_id"],
                         "off_pavement_frames": sorted(set(off_pavement))})
    episodes.sort(key=lambda event: event["start_frame"])
    if any(a["end_frame"] >= b["start_frame"] for a, b in zip(episodes, episodes[1:])):
        raise ValueError("Passing episodes overlap or lack a separating frame")
    if len(episodes) >= 2 and len({event["target_vehicle_id"] for event in episodes}) != 1:
        raise ValueError("Fixed overtaken vehicle differs between right-passing episodes")
    for label, values in (("speeding", speeding_frames), ("hazard", hazard_frames)):
        if not isinstance(values, list) or any(type(frame) is not int or frame not in index for frame in values):
            raise ValueError(label + " source frame missing")
    event_frames = list(speeding_frames) + list(hazard_frames)
    for event in episodes:
        event_frames.extend((event["start_frame"], event["end_frame"]))
    if not event_frames:
        raise ValueError("No source-linked conduct events")
    first, last = min(event_frames), max(event_frames)
    envelope = index[last]["distance_m"] - index[first]["distance_m"]
    return {"driver_id": driver, "first_conduct_frame": first,
            "last_conduct_frame": last, "conduct_envelope_m": envelope,
            "within_one_mile_envelope": envelope <= MILE_M,
            "right_passing_episode_count": len(episodes),
            "two_distinct_right_passing_episodes_measured": len(episodes) >= 2,
            "episodes": episodes, "speeding_source_frames": sorted(set(speeding_frames)),
            "hazard_source_frames": sorted(set(hazard_frames)),
            "speeding_violation_decided": False, "passing_violation_decided": False,
            "immediate_hazard_decided": False, "offense_decided": False}
