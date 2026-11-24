"""Measure rear vehicle, slowing, and warning timing from retained Native sources.

The acceleration and rear-gap thresholds are diagnostic engineering settings,
not statutory definitions of 'suddenly' or 'immediately'.
"""
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
RATE_HZ = 20


def measure(packet):
    if packet.get("format") != "prior-signal-native-source-v1":
        raise ValueError("wrong source packet format")
    if packet.get("rate_hz") != RATE_HZ:
        raise ValueError("20 Hz frame map required")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) != FRAMES:
        raise ValueError("600 source frames required")
    threshold = float(packet.get("deceleration_probe_mps2", -2.0))
    if not math.isfinite(threshold) or threshold >= 0:
        raise ValueError("diagnostic deceleration threshold must be negative")
    rows = []
    previous_speed = None
    for index, item in enumerate(frames):
        if item.get("frame") != index or abs(float(item.get("sim_time_s", -1)) - index / RATE_HZ) > 1e-6:
            raise ValueError("noncanonical frame map")
        for field in ("ego_velocity_source_ref", "rear_pose_source_ref", "rear_extent_source_ref",
                      "ego_pose_source_ref", "ego_extent_source_ref", "signal_source_ref"):
            if not item.get(field):
                raise ValueError("missing retained source: " + field)
        speed = float(item["ego_speed_mps"])
        gap = float(item["rear_surface_gap_m"])
        if not math.isfinite(speed) or speed < 0 or not math.isfinite(gap):
            raise ValueError("invalid speed or rear surface gap")
        if not isinstance(item.get("rear_same_lane"), bool) or not isinstance(item.get("rear_behind"), bool):
            raise ValueError("rear lane and direction must be sourced")
        signal = item.get("signal_request")
        if signal not in ("none", "brake_lamp", "hand_stop_or_slow", "both"):
            raise ValueError("unsupported signal request")
        if not isinstance(item.get("signal_observed"), bool):
            raise ValueError("signal observation required")
        acceleration = None if previous_speed is None else (speed - previous_speed) * RATE_HZ
        rows.append({"frame": index, "sim_time_s": index / RATE_HZ,
                     "ego_speed_mps": speed, "longitudinal_acceleration_mps2": acceleration,
                     "stopped_probe": speed <= 0.05,
                     "sudden_slow_probe": acceleration is not None and acceleration <= threshold,
                     "rear_surface_gap_m": gap, "rear_same_lane": item["rear_same_lane"],
                     "rear_behind": item["rear_behind"], "signal_request": signal,
                     "signal_observed": item["signal_observed"]})
        previous_speed = speed
    event = next((row for row in rows if row["stopped_probe"] or row["sudden_slow_probe"]), None)
    signal = next((row for row in rows if row["signal_observed"] and row["signal_request"] != "none"), None)
    prior = bool(event and signal and signal["frame"] < event["frame"])
    return {"format": "prior-signal-measurement-v1", "source_packet_sha256": hashlib.sha256(
                json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "diagnostic_threshold_mps2": threshold, "event_frame": event["frame"] if event else None,
            "event_kind": ("stop" if event["stopped_probe"] else "sudden_slow_probe") if event else None,
            "signal_first_frame": signal["frame"] if signal else None,
            "signal_precedes_event": prior,
            "signal_lead_frames": event["frame"] - signal["frame"] if event and signal else None,
            "rear_at_event": ({"same_lane": event["rear_same_lane"], "behind": event["rear_behind"],
                               "surface_gap_m": event["rear_surface_gap_m"]} if event else None),
            "legal_appropriateness": "requires independent original source review",
            "frames": rows}


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        raise SystemExit("usage: prior_signal_meter.py source.json output.json")
    result = measure(json.loads(Path(sys.argv[1]).read_text()))
    Path(sys.argv[2]).write_text(json.dumps(result, indent=2) + "\n")
