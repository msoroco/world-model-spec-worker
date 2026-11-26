"""Exercise both exact observed-source meters with labeled synthetic rows."""
import argparse
import json
from pathlib import Path

from observed_left_turn import ASSIGNMENT, measure


def rows(suffix):
    release = 300 if suffix == "a" else 180
    for frame in range(600):
        time_s = frame / 20
        turn = frame >= release
        yield {
            "case_id": ASSIGNMENT + "__selected_d457f261__condition_" + suffix,
            "source_kind": "synthetic_cpu", "frame": frame,
            "native_frame": 1000 + frame, "time_s": time_s,
            "ego": {"speed_mps": 4 if frame < 100 or turn else 0,
                    "left_turn_progress": min(1, (frame - release + 1) / 80) if turn else 0,
                    "distance_to_conflict_m": max(-2, 5 - max(0, frame - release) / 10),
                    "inside_intersection": frame >= 100,
                    "left_indicator_on": True},
            "oncoming": [
                {"actor_id": "initial", "speed_mps": 8,
                 "distance_to_conflict_m": 100 - 8 * time_s,
                 "approach_lane_opposite": True},
                {"actor_id": "subsequent", "speed_mps": 7 if frame < release + 10 else 4,
                 "distance_to_conflict_m": 140 - 7 * time_s,
                 "approach_lane_opposite": True},
            ],
        }


def prove(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for suffix in ("a", "b"):
        source = output / ("condition_" + suffix + "-observed.jsonl")
        source.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows(suffix)))
        results[suffix] = measure(source)
    if results["a"]["first_turn_progress_frame"] != 300 or results["b"]["first_turn_progress_frame"] != 180:
        raise AssertionError("Observed source conditions differ from selected request")
    if not results["a"]["initial_opponent_passed_before_turn"] or results["b"]["initial_opponent_passed_before_turn"]:
        raise AssertionError("Controlled initial-opponent passage contrast differs")
    if not all(result["subsequent_opponent_decelerated_after_turn"] for result in results.values()):
        raise AssertionError("Subsequent-opponent response source absent")
    return {"format": "c329654-observed-source-cpu-proof-v1", "cases": results,
            "source_kind": "synthetic_cpu", "original_native_executed": False,
            "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(prove(args.output), indent=2, sort_keys=True))
