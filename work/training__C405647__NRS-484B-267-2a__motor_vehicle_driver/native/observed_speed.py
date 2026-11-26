"""Measure the two speed interventions from joined Native observations.

The synthetic mode exercises the same frame checks for CPU preparation. Its
result is explicitly barred from being reported as physical or legal evidence.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
RATE = 20
ASSIGNMENT_ID = "training__C405647__NRS-484B-267-2a__motor_vehicle_driver"
BASE = ASSIGNMENT_ID + "__selected_d6045110__condition_"
CASES = {BASE + "a": "reduce_speed", BASE + "b": "maintain_speed"}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def measure(path, *, synthetic=False):
    source = Path(path)
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    _require(len(rows) == FRAMES, "Native observation window must have 600 frames")
    case = rows[0].get("case_id")
    _require(case in CASES, "Exact case identity missing")
    expected_provenance = "synthetic_cpu_fixture" if synthetic else "original_native_observation"
    previous_native = -1
    previous_distance = None
    first_pass = None
    lamp_states = []
    for index, row in enumerate(rows):
        _require(row.get("case_id") == case and row.get("source_kind") == expected_provenance,
                 "Source provenance or exact case differs")
        _require(row.get("video_frame") == index and _finite(row.get("time_s"))
                 and abs(row["time_s"] - index / RATE) < 1e-6,
                 "Original frame and time join differs")
        native = row.get("native_frame")
        _require(type(native) is int and native > previous_native, "Native frame identity is not increasing")
        previous_native = native
        ego = row.get("ego", {})
        other = row.get("qualifying_vehicle", {})
        for actor in (ego, other):
            _require(_finite(actor.get("road_x_m")) and _finite(actor.get("speed_mps"))
                     and actor["speed_mps"] >= 0, "Original actor motion source missing")
        _require(other.get("kind") == "authorized_emergency_vehicle"
                 and other.get("authorized_source_id") and other["speed_mps"] > 0,
                 "Moving authorized emergency vehicle source missing")
        _require(type(other.get("flashing_state")) is bool
                 and other.get("lamp_equipment_source_id") and other.get("lamp_qualification_source_id"),
                 "Qualifying flashing-light source missing")
        lamp_states.append(other["flashing_state"])
        _require(row.get("officer_direction_source_id") and row.get("officer_direction") is None,
                 "Officer exception absence source missing")
        _require(row.get("road_context_source_id") and row.get("weather_context_source_id")
                 and _finite(row.get("posted_limit_mps"))
                 and row.get("wet_road") is False and _finite(row.get("visibility_m")),
                 "Reasonable-speed context source missing")
        views = row.get("camera_frames", {})
        _require(set(views) == {"overview", "approach", "reference_corner", "driver_reference"}
                 and all(type(value) is int and value == native for value in views.values()),
                 "Four synchronized original camera frames missing")
        distance = other["road_x_m"] - ego["road_x_m"]
        if index == 0:
            _require(distance > 0, "Initial approach geometry missing")
        if index == 160:
            _require(previous_distance is not None and distance < rows[0]["qualifying_vehicle"]["road_x_m"] - rows[0]["ego"]["road_x_m"],
                     "Approach motion not observed")
        if distance <= 0 and first_pass is None:
            first_pass = index
        previous_distance = distance
    before = sum(r["ego"]["speed_mps"] for r in rows[0:120]) / 120
    after = sum(r["ego"]["speed_mps"] for r in rows[240:280]) / 40
    reduction = before - after
    _require(before > 0, "Initial ego travel missing")
    _require(any(lamp_states) and not all(lamp_states)
             and sum(lamp_states[i] != lamp_states[i-1] for i in range(1, FRAMES)) >= 2,
             "Flashing-light state transitions missing")
    _require(reduction > 3 if CASES[case] == "reduce_speed" else abs(reduction) < 0.5,
             "Measured speed intervention differs from selected condition")
    _require(first_pass is not None and first_pass >= 200,
             "Passing event must follow the approach intervention")
    if CASES[case] == "reduce_speed":
        crossing_speed = rows[first_pass]["ego"]["speed_mps"]
        _require(abs(crossing_speed - after) < 1, "Reduced speed not held while passing")
    return {"format": "c405647-observed-speed-v1", "case_id": case,
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "frames": FRAMES, "source_kind": expected_provenance,
            "speed_before_mps": round(before, 5), "speed_after_mps": round(after, 5),
            "reduction_mps": round(reduction, 5), "first_pass_frame": first_pass,
            "physical_completion_claimed": False,
            "reasonable_and_proper_legally_determined": False,
            "actual_pixels_reviewed": False, "fixture_only": synthetic}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--synthetic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(measure(args.source, synthetic=args.synthetic), indent=2, sort_keys=True))
