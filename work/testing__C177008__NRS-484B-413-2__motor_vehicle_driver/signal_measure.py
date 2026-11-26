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
DISTANCE_FEET = {"business": 100.0, "residential": 100.0, "other": 300.0}


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
    for key in ("highway_source", "district_source", "frontage_source", "building_use_source", "other_vehicle_source"):
        _require(isinstance(context.get(key), str) and context[key], f"missing {key}")
    tag = expected_case_id.rsplit("__", 1)[-1]
    expected_district = ("residential" if tag.startswith("residence_") else
                         "other" if tag.startswith("other_area_") else
                         "business" if tag.startswith("business_" ) else None)
    _require(expected_district is not None and context.get("district_kind") == expected_district,
             "selected district not established")
    _require(context.get("maneuver") == "right_turn", "wrong maneuver")
    rows = packet.get("samples")
    _require(isinstance(rows, list) and len(rows) >= 3, "missing sampled history")
    if packet.get("source_kind") == "original_native":
        _require(packet.get("diagnostic_fixture") is False, "diagnostic original source conflict")
        _require(packet.get("sampling_hz") == 20 and packet.get("frame_count") == 900
                 and len(rows) == 900, "incomplete original 20 Hz signal history")
        _require(isinstance(packet.get("site_sha256"), str)
                 and len(packet["site_sha256"]) == 64, "missing original site binding")
        for key in ("route_source", "driver_source", "camera_rig_source",
                    "right_turn_variant_source", "other_vehicle_actor_id"):
            _require(isinstance(context.get(key), str) and context[key],
                     "missing original fixed source: " + key)
        archives = packet.get("camera_archives", {})
        _require(set(archives) == {"overview", "approach", "reference_corner", "driver_reference"},
                 "missing original four-camera source")
        for name, archive in archives.items():
            _require(archive.get("frame_count") == 900 and isinstance(archive.get("sha256"), str)
                     and len(archive["sha256"]) == 64, "incomplete original camera source: " + name)
    frames = []
    times = []
    for row in rows:
        _require(all(k in row for k in ("frame", "x_m", "y_m", "right_signal", "course_change")), "missing source sample")
        _require(type(row["frame"]) is int and row["frame"] >= 0, "bad frame")
        _require(type(row["right_signal"]) is bool and type(row["course_change"]) is bool, "bad source state")
        _require(all(math.isfinite(float(row[k])) for k in ("x_m", "y_m")), "bad position")
        frames.append(row["frame"])
        if packet.get("source_kind") == "original_native":
            _require(math.isfinite(float(row.get("time_s")))
                     and set(row.get("camera_frames", {})) == set(archives),
                     "missing original time or camera join")
            times.append(float(row["time_s"]))
    _require(frames == sorted(set(frames)), "nonmonotonic or duplicate frames")
    _require(all(b - a == 1 for a, b in zip(frames, frames[1:])), "missing frames")
    if times:
        _require(all(abs(b - a - .05) <= 1e-4 for a, b in zip(times, times[1:])),
                 "original 20 Hz time gap")
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
    first_activation = next((i for i, row in enumerate(rows[:onset]) if row["right_signal"]), None)
    observed_interruptions = ([] if first_activation is None else
                              [row["frame"] for row in rows[first_activation:onset]
                               if not row["right_signal"]])
    if packet.get("source_kind") == "original_native":
        expected_weather = "rain" if tag == "business_rain" else "clear"
        _require(all(row.get("weather") == expected_weather for row in rows),
                 "original weather history differs from selected case")
    return {
        "format": "turn-signal-measurement-v1",
        "case_id": expected_case_id,
        "source_path": str(path),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "onset_frame": rows[onset]["frame"],
        "continuous_start_frame": rows[first]["frame"],
        "continuous_distance_m": metres,
        "continuous_distance_ft": feet,
        "statutory_reference_ft": DISTANCE_FEET[expected_district],
        "sampled_threshold_reached": feet >= DISTANCE_FEET[expected_district],
        "prior_inactive_frames": prior_interruptions,
        "interruption_frames_after_activation": observed_interruptions,
        "source_kind": packet.get("source_kind", "diagnostic_fixture"),
        "site_sha256": packet.get("site_sha256"),
        "weather_source": context.get("weather_source"),
        "district_kind": expected_district,
        "context_sources": {key: context.get(key) for key in ("highway_source", "district_source", "frontage_source", "building_use_source", "other_vehicle_source", "route_source", "driver_source", "camera_rig_source", "right_turn_variant_source", "other_vehicle_actor_id")},
        "limitations": ["Sampled path length is a lower bound between retained frames.", "Authored context sources require independent physical and statutory review."],
    }


def compare(left: dict, right: dict, comparison: str, above: dict | None = None) -> dict:
    _require(left["case_id"] != right["case_id"], "comparison duplicates a case")
    _require(above is None, "selected comparisons are exact pairs")
    _require(left.get("source_kind") == right.get("source_kind"),
             "source provenance differs")
    if comparison == "district_threshold":
        fixed = set(left["context_sources"]) - {"district_source", "frontage_source", "building_use_source"}
        _require(all(left["context_sources"][key] == right["context_sources"][key]
                     for key in fixed), "fixed route or actor context differs")
        _require(left["district_kind"] == "business" and right["district_kind"] == "other",
                 "district contrast missing")
        _require(left["statutory_reference_ft"] == 100.0 and
                 right["statutory_reference_ft"] == 300.0,
                 "statutory district references differ")
        _require(left["weather_source"] == right["weather_source"], "district weather differs")
    else:
        _require(left["context_sources"] == right["context_sources"] and
                 left.get("site_sha256") == right.get("site_sha256"),
                 "fixed Native site or context differs")
    if comparison == "lead_distance":
        _require(left["district_kind"] == right["district_kind"] == "business" and
                 left["weather_source"] == right["weather_source"], "distance context differs")
        _require(left["continuous_distance_ft"] >= 100 > right["continuous_distance_ft"],
                 "selected signal-distance contrast missing")
    elif comparison == "continuity":
        _require(left["district_kind"] == right["district_kind"] == "business" and
                 left["weather_source"] == right["weather_source"] and
                 not left["interruption_frames_after_activation"] and
                 right["interruption_frames_after_activation"],
                 "selected continuity contrast missing")
    elif comparison == "district_threshold":
        _require(left["continuous_distance_ft"] >= 100 and
                 right["continuous_distance_ft"] < 300,
                 "selected district-distance contrast missing")
    elif comparison == "weather_invariance":
        _require(left["sampled_threshold_reached"] and right["sampled_threshold_reached"], "signal distance changed")
        _require(left["weather_source"] != right["weather_source"], "weather contrast missing")
    else:
        raise ValueError("unknown comparison")
    return {"comparison_id": comparison,
            "case_ids": [left["case_id"], right["case_id"]] + ([above["case_id"]] if above is not None else []),
            "software_measurement_passed": True}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Measure saved Native signal samples")
    parser.add_argument("--source", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = measure(args.source, args.case_id)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
