"""Measure an original-frame left-turn sequence without making a legal finding.

The input is a saved actor readback, not an authored motion request. The local
capture must seal its Native source before this measurement is used for delivery.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


FRAMES = 600
RATE_HZ = 20
ASSIGNMENT = "training__C329654__NRS-484B-253__motor_vehicle_driver"
CASES = {ASSIGNMENT + "__selected_d457f261__condition_a",
         ASSIGNMENT + "__selected_d457f261__condition_b"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def measure(path):
    path = Path(path)
    records = [json.loads(line) for line in path.read_text().splitlines()]
    if len(records) != FRAMES:
        raise ValueError("Complete 600-frame observed actor source required")
    case_id = records[0].get("case_id")
    if case_id not in CASES:
        raise ValueError("Exact selected case identity differs")
    source_kind = records[0].get("source_kind")
    if source_kind not in ("original_native", "synthetic_cpu"):
        raise ValueError("Observed actor source provenance required")
    actor_ids = None
    native_frames = []
    for frame, row in enumerate(records):
        if row.get("case_id") != case_id or row.get("source_kind") != source_kind:
            raise ValueError("Case or provenance changes within observed source")
        if row.get("frame") != frame or not finite(row.get("time_s")) or abs(row["time_s"] - frame / RATE_HZ) > 1e-6:
            raise ValueError("Observed frame and time join differs")
        native = row.get("native_frame")
        if not isinstance(native, int) or isinstance(native, bool):
            raise ValueError("Missing original Native frame readback")
        native_frames.append(native)
        ego = row.get("ego", {})
        if not all(finite(ego.get(key)) for key in ("speed_mps", "left_turn_progress", "distance_to_conflict_m")):
            raise ValueError("Missing measured ego kinematics")
        if not 0 <= ego["left_turn_progress"] <= 1 or ego["speed_mps"] < 0:
            raise ValueError("Invalid measured ego kinematics")
        if ego.get("inside_intersection") not in (True, False) or ego.get("left_indicator_on") not in (True, False):
            raise ValueError("Missing original intersection or lamp readback")
        opponents = row.get("oncoming")
        if not isinstance(opponents, list) or len(opponents) < 2:
            raise ValueError("Initial and subsequent opposing actors required")
        ids = tuple(item.get("actor_id") for item in opponents)
        if len(set(ids)) != len(ids) or any(not isinstance(item, str) or not item for item in ids):
            raise ValueError("Opposing actor identity differs")
        if actor_ids is None:
            actor_ids = ids
        elif actor_ids != ids:
            raise ValueError("Opposing actor identity changes within source")
        for opponent in opponents:
            if not all(finite(opponent.get(key)) for key in ("speed_mps", "distance_to_conflict_m")):
                raise ValueError("Missing opposing actor kinematics")
            if opponent["speed_mps"] < 0 or opponent.get("approach_lane_opposite") is not True:
                raise ValueError("Opposing lane or speed readback differs")
    if any(b <= a for a, b in zip(native_frames, native_frames[1:])):
        raise ValueError("Original Native frame sequence is not increasing")
    turn = next((i for i, row in enumerate(records)
                 if row["ego"]["left_turn_progress"] > 0), None)
    if turn is None:
        raise ValueError("Measured left turn never starts")
    if not records[turn]["ego"]["inside_intersection"] or not all(
            row["ego"]["left_indicator_on"] for row in records[max(0, turn - 20):turn + 1]):
        raise ValueError("Measured intersection presence or signal is absent at turn")
    first_pass = next((i for i, row in enumerate(records)
                       if row["oncoming"][0]["distance_to_conflict_m"] <= 0), None)
    if first_pass is None:
        raise ValueError("Initial opponent never reaches conflict point")
    second_pass = next((i for i, row in enumerate(records)
                        if row["oncoming"][1]["distance_to_conflict_m"] <= 0), None)
    stopped_before_turn = any(row["ego"]["speed_mps"] < 0.1 for row in records[100:turn])
    if not stopped_before_turn:
        raise ValueError("No measured preturn yielding wait")
    second_speed_at_turn = records[turn]["oncoming"][1]["speed_mps"]
    later_second_speed = min(row["oncoming"][1]["speed_mps"] for row in records[turn:])
    return {
        "format": "c329654-observed-left-turn-v1", "case_id": case_id,
        "source_kind": source_kind, "source_sha256": digest(path),
        "frames": FRAMES, "rate_hz": RATE_HZ,
        "first_turn_progress_frame": turn,
        "first_opponent_conflict_frame": first_pass,
        "subsequent_opponent_conflict_frame": second_pass,
        "initial_opponent_passed_before_turn": first_pass < turn,
        "subsequent_opponent_speed_at_turn_mps": second_speed_at_turn,
        "subsequent_opponent_min_speed_after_turn_mps": later_second_speed,
        "subsequent_opponent_decelerated_after_turn": later_second_speed < second_speed_at_turn,
        "preturn_wait_observed": stopped_before_turn,
        "turn_signal_observed_before_and_at_turn": True,
        "subsequent_yield_response_observed": later_second_speed < second_speed_at_turn,
        "legal_immediate_hazard_threshold_asserted": False,
        "legal_priority_verdict": None,
        "physical_acceptance_claimed": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    print(json.dumps(measure(args.source), sort_keys=True))
