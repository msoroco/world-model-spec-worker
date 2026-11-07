"""Unselected C111294 speed-control candidates and source-measured gates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics

import geometry
import measure_speed

CANDIDATES = ("primary", "fallback1", "fallback2", "fallback3")
BASE_KNOBS = {"speed_pid_kp": 0.40, "steering_lookahead_m": 8.0,
              "brake_pid_kp": 0.30, "sample_rate_hz": 20,
              "duration_s": 24.0,
              "camera_profile": ["overview", "ego_forward", "ego_side", "junction"]}
CHANGED_KNOBS = {"primary": {},
                 "fallback1": {"speed_pid_kp": 0.55},
                 "fallback2": {"steering_lookahead_m": 11.0},
                 "fallback3": {"brake_pid_kp": 0.50}}
GATES = {
    "fallback1": {"metric": "approach_speed_shortfall_mph", "op": ">", "threshold": 0.75,
                  "source": "saved Native velocity in frames 0..99"},
    "fallback2": {"metric": "max_lane_center_error_m", "op": ">", "threshold": 0.35,
                  "source": "saved Native ego center x against authored lane center"},
    "fallback3": {"metric": "peak_speed_overshoot_mph", "op": ">", "threshold": 0.75,
                  "source": "saved Native peak velocity over all 480 frames"}}


def candidate_plan(case: str, candidate: str) -> dict:
    if case not in geometry.SPEED_MPH or candidate not in CANDIDATES:
        raise ValueError("Unknown case or candidate")
    return {"case_id": f"training__C111294__NRS-484B-600-1e__motor_vehicle_driver__{case}",
            "candidate": candidate, "law_id": "NRS-484B-600-1e", "cell_id": "C111294",
            "actor": "motor_vehicle_driver", "comparison_variable": "observed_speed",
            "requested_setting_mph": geometry.SPEED_MPH[case],
            "fixed_authored_road": "draft-fixtures/road.xodr",
            "fixed_other_actor_route": "opposing lane, x=-1.75 m, initial y=100 m, 10 m/s",
            "knobs": BASE_KNOBS | CHANGED_KNOBS[candidate],
            "changed_knobs": CHANGED_KNOBS[candidate],
            "fallback_trigger": GATES.get(candidate),
            "postcondition": "Remeasure 480 saved Native frames; preserve case source, legal context and intended speed relation",
            "status": "unselected_draft", "physical_effect_verified": False}


def measured_gates(case: str, source: Path, expected_sha256: str) -> dict:
    if case not in geometry.SPEED_MPH:
        raise ValueError("Unknown case")
    raw = Path(source).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Gate source hash changed")
    measurement = measure_speed.measure(source, expected_sha256)
    rows = [json.loads(line) for line in raw.splitlines()]
    approach = [sum(v * v for v in row["ego_velocity_mps"]) ** .5
                * measure_speed.MPS_TO_MPH for row in rows[:100]]
    return {"source_sha256": expected_sha256,
            "source_kind": rows[0].get("source_kind", "unlabelled"),
            "approach_speed_shortfall_mph": round(
                geometry.SPEED_MPH[case] - statistics.median(approach), 6),
            "max_lane_center_error_m": round(max(abs(row["ego_position_m"][0] - 1.75)
                                                  for row in rows), 6),
            "peak_speed_overshoot_mph": round(
                measurement["derived_peak_mph"] - geometry.SPEED_MPH[case], 6),
            "measured_relation": measurement["measured_relation"]}


def evaluate(case: str, candidate: str, source: Path, expected_sha256: str) -> dict:
    if candidate not in GATES:
        raise ValueError("Only fallbacks have a gate")
    metrics = measured_gates(case, source, expected_sha256)
    gate = GATES[candidate]
    value = metrics[gate["metric"]]
    return {"case": case, "candidate": candidate, "source_sha256": expected_sha256,
            "metric": gate["metric"], "observed": value,
            "threshold": gate["threshold"], "triggered": value > gate["threshold"],
            "source_kind": metrics["source_kind"],
            "physical_effect_verified": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    plans = [candidate_plan(case, candidate) for case in geometry.SPEED_MPH
             for candidate in CANDIDATES]
    if args.output:
        args.output.write_text(json.dumps(plans, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"unselected_draft_plans": len(plans),
                      "cases": len(geometry.SPEED_MPH),
                      "fallback_gates": list(GATES)}, sort_keys=True))
