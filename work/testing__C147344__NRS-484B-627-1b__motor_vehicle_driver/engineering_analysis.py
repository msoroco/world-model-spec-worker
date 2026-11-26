"""Saved-only engineering case finalizer with the original relation source."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from base_analysis import right_lane_follower_observation as _observe, saved_result, sha
from engineering_sweep_station import engineering_station


def right_lane_follower_observation(attempt: Path, case_id: str) -> dict:
    return _observe(attempt, case_id)


def right_lane_follower_observation_report(attempt: Path, case_id: str) -> dict:
    if engineering_station(case_id) is None:
        raise ValueError("exact engineering case required")
    observation = right_lane_follower_observation(attempt, case_id)
    trace = json.loads((attempt / "trace.json").read_text(encoding="utf-8"))
    rows = trace["frames"]
    speed_field = ("ego_speed_mps" if "__impediment-" in case_id else
                   "slower_vehicle_speed_mps")
    values = [row[speed_field] for row in rows]
    summary = {
        "original_frame_count": observation["original_frame_count"],
        "right_lane_frames": sum(row["ego_in_extreme_right_lane"]
                                 for row in observation["observations"]),
        "immediate_follower_frames": sum(row["follower_immediately_behind_in_ego_lane"]
                                         for row in observation["observations"]),
        "passing_frames": sum(row["passing_slower_vehicle_observed"]
                              for row in observation["observations"]),
        "speed_field": speed_field, "observed_mean_speed_mps": sum(values) / len(values),
        "legal_impediment_and_pass_necessity": "unresolved",
    }
    return {"format": "worker-analysis-report", "case_id": case_id,
            "measurements": {"right_lane_follower_observation": {
                "value": summary, "method": "right_lane_follower_observation",
                "sources": {"trace.json": sha(attempt / "trace.json"),
                            "relation.json": sha(attempt / "relation.json")}}},
            "analysis_complete": True, "diagnostic_fixture": trace.get("diagnostic_fixture") is True,
            "legal_verdict_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("fresh analysis report required")
    case_id = args.case or json.loads((args.attempt / "config.json").read_text())[
        "selected_case_id"]
    report = right_lane_follower_observation_report(args.attempt, case_id)
    result = saved_result(args.attempt, report)
    measured = report["measurements"]["right_lane_follower_observation"]["value"]
    speed_field = measured["speed_field"]
    result.setdefault("realized_observables", {})[speed_field] = {
        "value": measured["observed_mean_speed_mps"], "unit": "m/s",
        "method": "original 20 Hz Native actor speed readback, with full trace retained",
        "time_window": "entire original 45-second episode", "statistic": "mean",
        "reference": "channels/" + speed_field + ".jsonl",
        "sample_window_s": [0.0, 899 / 20],
    }
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    (args.attempt / "result.json").write_text(json.dumps(result, indent=2) + "\n",
                                              encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
