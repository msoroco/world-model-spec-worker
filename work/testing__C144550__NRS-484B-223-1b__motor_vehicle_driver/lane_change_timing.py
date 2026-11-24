"""Source-bound engineering timing for NRS 484B.223(1)(b).

This measures observable events. It does not decide legal signal
appropriateness, driver ascertainment, or whether movement was safe.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C144550__NRS-484B-223-1b__motor_vehicle_driver"


def _source(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}


def measure(source_path: str | Path) -> dict:
    """Measure first reported left-signal onset and center departure.

    The input is an original sampled trace export, not an authored target.
    Each frame must carry original pose, lateral offset from the source-lane
    center, left/right API signal states and an independent driver-check
    observation. All samples through departure are retained by index.
    """
    path = Path(source_path)
    trace = json.loads(path.read_text(encoding="utf-8"))
    return measure_trace(trace, _source(path))


def measure_trace(trace: dict, source: dict) -> dict:
    """Measure joined original samples with their independently sealed source."""
    if trace.get("assignment_id") != ASSIGNMENT:
        raise ValueError("assignment identity mismatch")
    if not trace.get("original_trace_id") or not trace.get("source_lane_id"):
        raise ValueError("original trace and source lane identities required")
    frames = trace.get("frames")
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError("at least three original frames required")
    for i, frame in enumerate(frames):
        for key in ("t_s", "x_m", "y_m", "source_lane_offset_m"):
            value = frame.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"frame {i}: finite {key} required")
        for key in ("left_signal", "right_signal", "driver_check_observed"):
            if not isinstance(frame.get(key), bool):
                raise ValueError(f"frame {i}: original boolean {key} required")
        if i and frame["t_s"] <= frames[i - 1]["t_s"]:
            raise ValueError("original frame times must strictly increase")
        if i and frame["t_s"] - frames[i - 1]["t_s"] > 0.075:
            raise ValueError("missing samples around event window")
    baseline = frames[0]["source_lane_offset_m"]
    departure = next((i for i, f in enumerate(frames) if abs(f["source_lane_offset_m"] - baseline) > 0.05), None)
    if departure is None:
        raise ValueError("no center departure in original trace")
    if departure == 0:
        raise ValueError("trace begins after departure")
    signal = next((i for i, f in enumerate(frames[: departure + 1]) if f["left_signal"] and not f["right_signal"]), None)
    check = next((i for i, f in enumerate(frames[:departure]) if f["driver_check_observed"]), None)
    lead_distance = None
    if signal is not None:
        lead_distance = sum(
            math.hypot(frames[i]["x_m"] - frames[i - 1]["x_m"], frames[i]["y_m"] - frames[i - 1]["y_m"])
            for i in range(signal + 1, departure + 1)
        )
    return {
        "assignment_id": ASSIGNMENT,
        "original_trace_id": trace["original_trace_id"],
        "source_lane_id": trace["source_lane_id"],
        "source": source,
        "method": "planar_original_pose_path_integral_signal_to_first_center_displacement_gt_0.05m",
        "signal_onset_index": signal,
        "signal_precedes_center_departure": signal is not None and signal < departure,
        "departure_bracket_indices": [departure - 1, departure],
        "driver_check_observed_before_departure": check is not None,
        "driver_check_index": check,
        "signal_lead_distance_m": lead_distance,
        "evidentiary_limit": "Observed check is not proof of driver ascertainment or movement safety; this is not a legal cutoff or judgment.",
    }
