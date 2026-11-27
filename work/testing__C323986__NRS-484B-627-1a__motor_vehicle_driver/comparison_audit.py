"""Audit exact source-bound comparison pairs and engineering sweeps."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
AXIS = {
    "right_side_position": "ego_body_right_edge_m",
    "paved_width_condition": "paved_right_edge_m",
    "immediate_follower_condition": "follower_lane_id",
    "obstruction_effect": "obstruction_station_m",
    "impediment_engineering_sweep": "ego_speed_mps",
    "paved_width_engineering_sweep": "paved_right_edge_m",
    "right_position_engineering_sweep": "ego_body_right_edge_m",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(comparison: str, attempts: list[Path]) -> dict:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    matches = [row for row in plan["comparisons"] if row["comparison_id"] == comparison]
    if len(matches) != 1 or comparison not in AXIS:
        raise ValueError("unknown exact comparison")
    expected = matches[0]["case_ids"]
    if len(attempts) != len(expected):
        raise ValueError("comparison case count differs")
    values, hashes, reports, fixed = [], [], [], []
    for case, attempt in zip(expected, attempts):
        motion_path = attempt / "original-motion.json"
        motion = json.loads(motion_path.read_text())
        mapping = attempt / "original-frame-map.json"
        config = json.loads((attempt / "config.json").read_text())
        report = json.loads((attempt / "analysis-report.json").read_text())
        if (motion.get("case_id") != case or config.get("selected_case_id") != case or
                report.get("case_id") != case):
            raise ValueError("comparison exact case differs")
        if motion.get("original_frame_map_sha256") != digest(mapping):
            raise ValueError("comparison original frame map differs")
        rows = motion.get("frames", [])
        if not rows or any(row.get("ego_actor_id") is None for row in rows):
            raise ValueError("comparison original actor missing")
        first = rows[0]
        if AXIS[comparison] not in first:
            raise ValueError("comparison axis measurement missing")
        values.append(first[AXIS[comparison]])
        hashes.append(digest(motion_path))
        reports.append(digest(attempt / "analysis-report.json"))
        fixed.append({key: config.get(key) for key in
                      ("law_id", "cell_id", "actor", "rate_hz", "duration_s", "cameras")})
    if any(item != fixed[0] for item in fixed[1:]):
        raise ValueError("comparison fixed capture contract differs")
    if len(set(values)) != len(values):
        raise ValueError("comparison measured axis does not differ")
    return {"comparison_id": comparison, "case_ids": expected,
            "axis": AXIS[comparison], "observed_values": values,
            "source_sha256": hashes, "analysis_sha256": reports,
            "fixed_capture_contract": True, "legal_verdict_claimed": False,
            "physical_acceptance_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--attempt", action="append", type=Path, required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    attempts = args.attempt
    if args.negative:
        attempts = [attempts[0]] * len(attempts)
        try:
            audit(args.comparison, attempts)
        except ValueError as error:
            if str(error) != "comparison exact case differs":
                raise
            print(str(error))
            raise SystemExit(2)
        raise AssertionError("mismatched comparison case accepted")
    print(json.dumps(audit(args.comparison, attempts), sort_keys=True))


if __name__ == "__main__":
    main()
