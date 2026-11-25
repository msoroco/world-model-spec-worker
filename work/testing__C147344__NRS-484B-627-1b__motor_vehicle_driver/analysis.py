"""Selected saved-source measurement report; original status is source-gated."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from finalize_follower import finalize
from reviewed_scene import ASSIGNMENT, VARIANTS


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def right_lane_follower_observation(attempt: Path, case_id: str) -> dict:
    trace, relation = attempt / "trace.json", attempt / "relation.json"
    for path in (trace, relation):
        if not path.is_file():
            raise ValueError("Missing required source: " + path.name)
    return finalize(trace, sha(trace), relation, sha(relation), case_id)


def build_report(attempt: Path, case_id: str) -> dict:
    attempt = Path(attempt)
    if case_id not in {ASSIGNMENT + "__" + suffix for suffix in VARIANTS}:
        raise ValueError("exact selected case required")
    observation = right_lane_follower_observation(attempt, case_id)
    trace = json.loads((attempt / "trace.json").read_text(encoding="utf-8"))
    value = {"original_frame_count": observation["original_frame_count"],
             "right_lane_frames": sum(row["ego_in_extreme_right_lane"] for row in observation["observations"]),
             "immediate_follower_frames": sum(row["follower_immediately_behind_in_ego_lane"] for row in observation["observations"]),
             "passing_frames": sum(row["passing_slower_vehicle_observed"] for row in observation["observations"]),
             "legal_impediment_and_pass_necessity": "unresolved"}
    return {"format": "worker-analysis-report", "case_id": case_id,
            "measurements": {"right_lane_follower_observation": {
                "value": value, "method": "right_lane_follower_observation",
                "sources": {"trace.json": sha(attempt / "trace.json"),
                            "relation.json": sha(attempt / "relation.json")}}},
            "analysis_complete": True,
            "diagnostic_fixture": trace.get("diagnostic_fixture") is True,
            "legal_verdict_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("fresh analysis report required")
    report = build_report(args.attempt, args.case)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
