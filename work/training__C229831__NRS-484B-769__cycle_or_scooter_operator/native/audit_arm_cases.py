"""Independent saved-source audit for the three exact rider-arm probes.

This reviews original source joins and observed geometry. It never makes a
legal finding or treats diagnostic fixture pixels as physical visibility.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from finalize_sources import analyze
from runner import CASES


def audit_case(root: Path, case_id: str, *, diagnostic_fixture: bool = False):
    if case_id not in CASES:
        raise ValueError("Unknown exact rider-arm case")
    root = Path(root)
    diagnostic = analyze(root, allow_fixture=diagnostic_fixture)
    rows = [json.loads(line) for line in (root / "rider_arm.jsonl").read_text().splitlines()]
    intended = CASES[case_id]
    requested = [row.get("requested_method") for row in rows]
    if any(value != (intended if 100 <= index < 140 else "none")
           for index, value in enumerate(requested)):
        raise ValueError("Exact case arm control window differs")
    right_runs = diagnostic["right_horizontal"]["right_arm_horizontal_rightward_runs"]
    right_frames = {frame for run in right_runs
                    for frame in range(run["first_frame"], run["last_frame"] + 1)}
    left_frames = set(diagnostic["left_upward"]["left_arm_upward_frames"])
    window = set(range(100, 140))
    if intended == "right_horizontal" and not window <= right_frames:
        raise ValueError("Original right-horizontal arm geometry not observed in signal window")
    if intended == "left_upward" and not window <= left_frames:
        raise ValueError("Original left-upward arm geometry not observed in signal window")
    if intended == "none" and (right_frames & window or left_frames & window):
        raise ValueError("No-signal probe contains observed arm signal geometry")
    return {
        "format": "worker-independent-rider-arm-source-audit",
        "case_id": case_id,
        "source_hashes": diagnostic["source_hashes"],
        "requested_method": intended,
        "signal_window_frames": [100, 139],
        "right_observed_frames_in_window": len(right_frames & window),
        "left_observed_frames_in_window": len(left_frames & window),
        "roadway_occupied_frames": diagnostic["right_horizontal"]["roadway_occupied_frames"],
        "right_turn_route_frames": diagnostic["right_horizontal"]["right_turn_route_frames"],
        "source_join_passed": True,
        "diagnostic_fixture": diagnostic_fixture,
        "physical_visibility_verified": False,
        "legal_conclusion": None,
    }


def audit_comparison(roots: dict[str, Path], case_ids: list[str], *,
                     diagnostic_fixture: bool = False):
    if len(case_ids) != 2 or len(set(case_ids)) != 2:
        raise ValueError("Two different exact cases required")
    reports = [audit_case(roots[case], case, diagnostic_fixture=diagnostic_fixture)
               for case in case_ids]
    contexts = [json.loads((Path(roots[case]) / "road_context.json").read_text())
                for case in case_ids]
    fixed = ("machine_class", "authored_road_sha256", "map_readback_sha256",
             "roadway_polygon_xy_m", "right_turn_route_xy_m")
    for key in fixed:
        if contexts[0].get(key) != contexts[1].get(key):
            raise ValueError("Comparison fixed condition differs: " + key)
    if reports[0]["requested_method"] == reports[1]["requested_method"]:
        raise ValueError("Comparison hand-arm methods do not differ")
    return {"format": "worker-independent-rider-arm-comparison-audit",
            "case_ids": case_ids, "case_source_audits": reports,
            "fixed_conditions_checked": list(fixed),
            "observed_difference": "requested and measured arm pose in original signal window",
            "diagnostic_fixture": diagnostic_fixture,
            "physical_visibility_verified": False, "legal_conclusion": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit_case(args.source_dir, args.case,
        diagnostic_fixture=args.diagnostic_fixture), indent=2, allow_nan=False) + "\n")
