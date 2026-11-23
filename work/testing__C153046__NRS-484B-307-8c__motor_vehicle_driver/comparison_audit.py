"""Independently compare exact saved red-left measurements and fixed sources.

This checks measured variables on original-format traces. CPU fixtures do not
prove actual physical delivery or the legal classification of a maneuver.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from build_case_plan import AID, PAIRS

METRIC = {"stop_before_turn": "engineering_stop_observed",
          "extreme_left_position": "first_approach_lane_id",
          "receiving_direction": "receiving_direction_request",
          "pedestrian_yield": "pedestrian_conflict_at_crossing",
          "traffic_yield": "traffic_conflict_at_crossing"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _metrics(row: dict) -> dict:
    conflicts = row.get("conflicts_at_first_boundary_crossing")
    if not isinstance(conflicts, dict):
        raise ValueError("comparison lacks boundary crossing and conflict observation")
    return {"engineering_stop_observed": row.get("engineering_stop_observed"),
            "first_approach_lane_id": row.get("first_approach_lane_id"),
            "receiving_direction_request": row.get("receiving_direction_request"),
            "pedestrian_conflict_at_crossing": conflicts.get("pedestrian"),
            "traffic_conflict_at_crossing": conflicts.get("other_traffic")}


def compare(left_path: Path, right_path: Path, comparison_id: str) -> dict:
    if comparison_id not in PAIRS:
        raise ValueError("unknown exact comparison")
    left = json.loads(Path(left_path).read_text())
    right = json.loads(Path(right_path).read_text())
    expected_left, expected_right, _ = PAIRS[comparison_id]
    if (left.get("case_id") != AID + "__" + expected_left or
            right.get("case_id") != AID + "__" + expected_right or
            left.get("format") != "c153046-source-bound-measurement-draft" or
            right.get("format") != "c153046-source-bound-measurement-draft"):
        raise ValueError("comparison case identity or measurement format differs")
    for key in ("frames", "first_boundary_crossing_frame", "signal_red_frames", "signal_actor_id"):
        if not left.get(key) or left[key] != right.get(key):
            raise ValueError("comparison fixed original frame/signal condition differs: " + key)
    left_hashes, right_hashes = left.get("source_hashes"), right.get("source_hashes")
    if not isinstance(left_hashes, dict) or set(left_hashes) != {"opendrive", "signal_authority",
            "approach_lanes", "receiving_lanes", "stop_boundary"} or set(left_hashes) != set(right_hashes):
        raise ValueError("comparison source inventory missing")
    changed_sources = {key for key in left_hashes if left_hashes[key] != right_hashes[key]}
    expected_sources = {"receiving_lanes"} if comparison_id == "receiving_direction" else set()
    if changed_sources != expected_sources:
        raise ValueError("comparison fixed source changed or declared source did not change")
    left_metrics, right_metrics = _metrics(left), _metrics(right)
    selected = METRIC[comparison_id]
    if left_metrics[selected] == right_metrics[selected]:
        raise ValueError("declared measured difference absent: " + selected)
    for key in left_metrics:
        if key != selected and left_metrics[key] != right_metrics[key]:
            raise ValueError("undeclared measured difference: " + key)
    return {"format": "c153046-independent-comparison-protocol", "comparison_id": comparison_id,
            "case_ids": [left["case_id"], right["case_id"]],
            "left_measurement_sha256": sha(Path(left_path)),
            "right_measurement_sha256": sha(Path(right_path)),
            "changed_metric": selected, "changed_sources": sorted(changed_sources),
            "fixed_original_conditions_checked": True,
            "passed": True, "physical_acceptance_claimed": False,
            "legal_judgment": "unresolved"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left", required=True)
    parser.add_argument("--right", required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("retain previous comparison audit")
    result = compare(Path(args.left), Path(args.right), args.comparison)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(result["comparison_id"], result["changed_metric"], result["passed"])


if __name__ == "__main__":
    main()
