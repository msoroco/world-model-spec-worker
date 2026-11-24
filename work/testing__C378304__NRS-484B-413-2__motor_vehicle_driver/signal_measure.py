"""Saved-source measurements for the NRS 484B.413(2) right-turn probes.

This module measures recorded samples. It does not infer legality from a
controller request, a case name, or an accepted-recording label.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

FEET_PER_METRE = 3.280839895013123
BUSINESS_DISTANCE_FEET = 100.0


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def measure(source_path: str | Path, expected_case_id: str) -> dict:
    path = Path(source_path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    _require(packet.get("case_id") == expected_case_id, "wrong case identity")
    _require(packet.get("format") == "native-turn-signal-samples-v1", "wrong source format")
    _require(packet.get("ego_actor") == "motor_vehicle_driver", "wrong ego actor")
    context = packet.get("context", {})
    for key in ("highway_source", "district_source", "frontage_source", "building_use_source", "loading_zone_source"):
        _require(isinstance(context.get(key), str) and context[key], f"missing {key}")
    _require(context.get("district_kind") == "business", "business district not established")
    _require(context.get("maneuver") == "right_turn", "wrong maneuver")
    rows = packet.get("samples")
    _require(isinstance(rows, list) and len(rows) >= 3, "missing sampled history")
    frames = []
    for row in rows:
        _require(all(k in row for k in ("frame", "x_m", "y_m", "right_signal", "course_change")), "missing source sample")
        _require(type(row["frame"]) is int and row["frame"] >= 0, "bad frame")
        _require(type(row["right_signal"]) is bool and type(row["course_change"]) is bool, "bad source state")
        _require(all(math.isfinite(float(row[k])) for k in ("x_m", "y_m")), "bad position")
        frames.append(row["frame"])
    _require(frames == sorted(set(frames)), "nonmonotonic or duplicate frames")
    _require(all(b - a == 1 for a, b in zip(frames, frames[1:])), "missing frames")
    changes = [i for i, row in enumerate(rows) if row["course_change"]]
    _require(changes and changes[0] > 0, "missing course-change onset")
    onset = changes[0]
    _require(not any(r["course_change"] for r in rows[:onset]), "ambiguous course-change onset")
    _require(rows[onset]["right_signal"], "signal absent at course-change onset")
    # Last continuous active interval before actual onset. Discrete samples
    # make the distance a lower bound; require a pre-onset sample at the
    # statutory boundary before claiming threshold coverage.
    first = onset
    while first > 0 and rows[first - 1]["right_signal"]:
        first -= 1
    metres = sum(math.hypot(
        float(rows[i]["x_m"]) - float(rows[i - 1]["x_m"]),
        float(rows[i]["y_m"]) - float(rows[i - 1]["y_m"]),
    ) for i in range(first + 1, onset + 1))
    feet = metres * FEET_PER_METRE
    prior_interruptions = [r["frame"] for r in rows[:first] if not r["right_signal"]]
    return {
        "format": "turn-signal-measurement-v1",
        "case_id": expected_case_id,
        "source_path": str(path),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "onset_frame": rows[onset]["frame"],
        "continuous_start_frame": rows[first]["frame"],
        "continuous_distance_m": metres,
        "continuous_distance_ft": feet,
        "statutory_reference_ft": BUSINESS_DISTANCE_FEET,
        "sampled_threshold_reached": feet >= BUSINESS_DISTANCE_FEET,
        "prior_inactive_frames": prior_interruptions,
        "weather_source": context.get("weather_source"),
        "context_sources": {key: context[key] for key in ("highway_source", "district_source", "frontage_source", "building_use_source", "loading_zone_source")},
        "limitations": ["Sampled path length is a lower bound between retained frames.", "Authored context sources require independent physical and statutory review."],
    }


def compare(left: dict, right: dict, comparison: str) -> dict:
    _require(left["case_id"] != right["case_id"], "comparison duplicates a case")
    _require(left["context_sources"] == right["context_sources"], "fixed context differs")
    if comparison == "business_right_distance":
        _require(left["continuous_distance_ft"] < 100 <= right["continuous_distance_ft"], "distance contrast missing")
    elif comparison == "signal_continuity":
        _require(left["sampled_threshold_reached"] and not right["sampled_threshold_reached"], "continuity contrast missing")
        _require(right["prior_inactive_frames"], "interruption absent")
    elif comparison == "regardless_weather":
        _require(left["sampled_threshold_reached"] and right["sampled_threshold_reached"], "signal distance changed")
        _require(left["weather_source"] != right["weather_source"], "weather contrast missing")
    else:
        raise ValueError("unknown comparison")
    return {"comparison_id": comparison, "case_ids": [left["case_id"], right["case_id"]], "software_measurement_passed": True}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Measure saved Native signal samples")
    parser.add_argument("--source", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = measure(args.source, args.case_id)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
