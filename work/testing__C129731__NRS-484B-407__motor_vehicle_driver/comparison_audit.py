"""Independently remeasure both accepted-reuse candidates in a declared pair.

This audit only reports source-bound geometric measurements. It cannot validate
the accepted metadata or decide what another driver actually perceived.
"""
from __future__ import annotations

import json
from pathlib import Path

from sight_measurement import DIRECTIONS, LIMIT_M, STATIONS_M, _source, measure


def audit(plan: dict, comparison_id: str, left_root: Path, left_inventory: dict,
          right_root: Path, right_inventory: dict) -> dict:
    pairs = [row for row in plan.get("accepted_comparisons_pending_original_review", [])
             if row.get("comparison_id") == comparison_id]
    if len(pairs) != 1:
        raise ValueError("unknown or duplicated accepted comparison")
    pair = pairs[0]
    if (len(pair.get("case_ids", [])) != 2 or len(pair.get("recording_ids", [])) != 2 or
            [left_inventory.get("case_id"), right_inventory.get("case_id")] != pair["case_ids"] or
            [left_inventory.get("recording_id"), right_inventory.get("recording_id")] != pair["recording_ids"]):
        raise ValueError("accepted comparison case or recording identity mismatch")
    left = measure(left_root, left_inventory, pair["case_ids"][0])
    right = measure(right_root, right_inventory, pair["case_ids"][1])
    for value in (left, right):
        if (value["original_frames"] != 900 or value["statutory_distance_m"] != LIMIT_M or
                value["station_distances_m"] != list(STATIONS_M) or
                value["observer_height_m"] != 1.4 or
                value["driver_visibility_judgment"] != "unresolved"):
            raise ValueError("comparison measurement contract changed")
    if left["source_sha256"]["road_geometry"] != right["source_sha256"]["road_geometry"]:
        raise ValueError("fixed road geometry source changed")
    if left["location_kind"] != right["location_kind"]:
        raise ValueError("fixed curve or crest location changed")
    if left["source_sha256"]["sight_rays"] == right["source_sha256"]["sight_rays"]:
        raise ValueError("original sight-ray source was reused")
    left_rays = _source(Path(left_root), left_inventory["sources"]["sight_rays"])["samples"]
    right_rays = _source(Path(right_root), right_inventory["sources"]["sight_rays"])["samples"]
    def blocked(rows):
        return {direction: sorted({row["station_distance_m"] for row in rows
                                   if row["direction"] == direction and not any(row["body_point_clear"])})
                for direction in DIRECTIONS}
    left_pattern, right_pattern = blocked(left_rays), blocked(right_rays)
    if left_pattern == right_pattern:
        raise ValueError("declared sight difference absent from original rays")
    if comparison_id != "discontinuous_reversal":
        direction = ("ahead_opposing" if comparison_id.endswith("ahead_opposing")
                     else "behind_same_direction")
        if (left["blocked_ray_counts"][direction] != 0 or
                right["blocked_ray_counts"][direction] <= 0):
            raise ValueError("declared direction difference absent from original rays")
    return {
        "format": "c129731-accepted-reuse-comparison-measurement-v1",
        "comparison_id": comparison_id,
        "case_ids": pair["case_ids"], "recording_ids": pair["recording_ids"],
        "source_sha256": [left["source_sha256"], right["source_sha256"]],
        "location_kind": left["location_kind"],
        "blocked_stations_m": [left_pattern, right_pattern],
        "blocked_ray_counts": [left["blocked_ray_counts"], right["blocked_ray_counts"]],
        "driver_visibility_judgment": "unresolved",
        "accepted_reuse_review": "pending_original_video_and_context_review",
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--left-attempt", type=Path, required=True)
    parser.add_argument("--right-attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite comparison measurement")
    plan = json.loads(args.plan.read_text())
    left_inv = json.loads((args.left_attempt / "inventory.json").read_text())
    right_inv = json.loads((args.right_attempt / "inventory.json").read_text())
    result = audit(plan, args.comparison, args.left_attempt, left_inv,
                   args.right_attempt, right_inv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
