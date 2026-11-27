"""Saved-source measurement report for the exact conditional right-side duty."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from finalize_original import finalize
from reviewed_scene import ASSIGNMENT, VARIANTS


def _source(attempt: Path, name: str) -> tuple[dict, str]:
    path = attempt / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def build_report(attempt: Path, case_id: str) -> dict:
    attempt = Path(attempt)
    if case_id not in {ASSIGNMENT + "__" + suffix for suffix in VARIANTS}:
        raise ValueError("exact selected case required")
    site, site_sha = _source(attempt, "original-site.json")
    if site.get("case_id") != case_id or not site.get("site_ref_sha256"):
        raise ValueError("original exact site source mismatch")
    measured = finalize(attempt, case_id)
    observations = measured["observations"]
    motion_sha = measured["source"]["motion_sha256"]
    relation_sha = measured["source"]["relation_sha256"]
    frame_sha = measured["source"]["frame_map_sha256"]
    motion = {"original-motion.json": motion_sha,
              "original-relation.json": relation_sha,
              "original-frame-map.json": frame_sha}
    site_source = {"original-site.json": site_sha}
    right_source = dict(motion, **site_source)
    measurements = {
        "following_motion_measurement": {
            "value": {"frame_count": 900,
                      "immediate_follower_frames": sum(row["immediately_behind_readback"] for row in observations),
                      "mean_subject_speed_mps": sum(row["subject_speed_mps"] for row in observations) / 900,
                      "mean_follower_speed_mps": sum(row["follower_speed_mps"] for row in observations) / 900,
                      "first_gap_m": observations[0]["follower_along_route_body_gap_m"],
                      "last_gap_m": observations[-1]["follower_along_route_body_gap_m"]},
            "method": "build_report", "sources": motion},
        "right_side_and_obstruction_measurement": {
            "value": {"frame_count": 900,
                      "first_ego_to_paved_edge_m": observations[0]["ego_to_paved_right_edge_m"],
                      "last_ego_to_paved_edge_m": observations[-1]["ego_to_paved_right_edge_m"],
                      "first_obstruction_to_paved_edge_m": observations[0]["obstruction_to_paved_right_edge_m"],
                      "lateral_obstruction_overlap_frames": sum(row["body_overlaps_obstruction_laterally"] for row in observations),
                      "reviewed_site_ref_sha256": site["site_ref_sha256"]},
            "method": "build_report", "sources": right_source},
        "nrs_484b_630_context": {
            "value": {"cross_reference": "NRS 484B.630",
                      "applicability": "unresolved by this physical measurement",
                      "context_source": site.get("nrs_484b_630_context_source", "not provided"),
                      "original_site_ref_sha256": site["site_ref_sha256"]},
            "method": "build_report", "sources": site_source},
    }
    return {"format": "worker-analysis-report", "case_id": case_id,
            "measurements": measurements,
            "original_frame_count": 900,
            "original_observations": observations,
            "diagnostic_fixture": site.get("cpu_test_synthetic_only") is True,
            "legal_verdict_claimed": False,
            "analysis_complete": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("fresh saved-source analysis report required")
    report = build_report(args.attempt, args.case)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
