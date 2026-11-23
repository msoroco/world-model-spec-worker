"""Independent source-hashed CPU comparisons for the selected right-turn cases.

This checks diagnostic source isolation and measurements. Legal and Native
acceptance remain unresolved.
"""

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOT = REPO / ".runtime-work/c412593-physical-preflight"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(comparison_id, mutate_camera=False, attempt_map=None):
    plan = json.loads((HERE / "case-plan.json").read_text())
    comparison = next(c for c in plan["comparisons"] if c["comparison_id"] == comparison_id)
    rows = []
    for case_id in comparison["case_ids"]:
        short = case_id.split("__")[-1]
        if attempt_map is None:
            folder = ROOT / (short + "-compat-primary")
            if short == "right_business_at_100_ft":
                folder = ROOT / "compat-primary"
        else:
            require(case_id in attempt_map, "Comparison attempt map omits case: " + case_id)
            folder = Path(attempt_map[case_id]).resolve()
        config = json.loads((folder / "config.json").read_text())
        report = json.loads((folder / "analysis-report.json").read_text())
        context = json.loads((folder / "route_context.json").read_text())
        require(config["selected_case_id"] == case_id and report["case_id"] == case_id,
                "Comparison source identity differs")
        for path, digest in report["source_hashes"].items():
            require(sha(folder / path) == digest, "Comparison source hash differs: " + path)
        measurement = report["source_report"]["measurement"]
        for path, digest in measurement["sources"].items():
            require(sha(folder / path) == digest, "Measurement source hash differs: " + path)
        rows.append({"case_id": case_id, "config": config, "context": context,
                     "report_sha256": sha(folder / "analysis-report.json"),
                     "measured_distance_m": measurement["turn_onset"]["continuous_right_signal_distance_m"],
                     "boundary_m": measurement["required_distance_m"],
                     "meets_boundary": measurement["observed_continuous_distance_meets_boundary"]})
    if mutate_camera:
        rows[-1]["config"]["cameras"][0]["width"] += 1
    for key in ("course", "rate_hz", "duration_s", "cameras", "actor", "requested_speed_mps"):
        require(all(row["config"][key] == rows[0]["config"][key] for row in rows),
                "Fixed comparison condition differs: " + key)
    for key in ("native_map_id", "approach_road_id", "approach_lane_id",
                "outgoing_road_id", "outgoing_lane_id", "turn_onset_frame"):
        require(all(row["context"][key] == rows[0]["context"][key] for row in rows),
                "Fixed route source differs: " + key)
    distances = [row["measured_distance_m"] for row in rows]
    if comparison_id in ("business_signal_distance", "other_signal_distance"):
        require(len(rows) == 3, "Distance comparison needs below/at/above")
        require(all(row["context"]["district_type"] == rows[0]["context"]["district_type"] for row in rows),
                "District differs within distance comparison")
        require(all(a < b for a, b in zip(distances, distances[1:])),
                "Source-measured distances lack strict below/at/above order")
        require([row["meets_boundary"] for row in rows] == [False, True, True],
                "Measured boundary classifications differ")
        require(all(row["boundary_m"] == rows[0]["boundary_m"] for row in rows),
                "Distance threshold differs within district")
    elif comparison_id == "continuity":
        require(len(rows) == 2 and rows[0]["config"]["case"]["signal_target_ft"] ==
                rows[1]["config"]["case"]["signal_target_ft"],
                "Continuity comparison changes planned signal target")
        require(rows[0]["context"]["district_type"] == rows[1]["context"]["district_type"],
                "Continuity comparison changes district")
        require(distances[0] > distances[1] and rows[0]["meets_boundary"] and
                not rows[1]["meets_boundary"], "Interruption is not source measured")
    else:
        raise ValueError("Unknown comparison")
    return {"format": "worker-c412593-comparison-audit", "comparison_id": comparison_id,
            "members": [{key: row[key] for key in ("case_id", "report_sha256", "measured_distance_m",
                                                   "boundary_m", "meets_boundary")} for row in rows],
            "fixed_conditions_passed": True, "diagnostic_fixture": True,
            "legal_conclusion": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", choices=("business_signal_distance", "other_signal_distance", "continuity"), required=True)
    parser.add_argument("--mutate-camera", action="store_true")
    parser.add_argument("--attempt-map", help="JSON map from exact case IDs to current compatibility attempts")
    parser.add_argument("--output")
    args = parser.parse_args()
    attempt_map = json.loads(Path(args.attempt_map).read_text()) if args.attempt_map else None
    result = audit(args.comparison, args.mutate_camera, attempt_map)
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))
