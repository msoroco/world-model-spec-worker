"""Independently compare three source-bound signal postures per covered kind."""

import argparse
import json
from pathlib import Path

from signal_measurements import measure


PACKAGE = Path(__file__).resolve().parent
PLAN = json.loads((PACKAGE / "case-plan.json").read_text())


def compare(comparison_id, attempts, diagnostic=False):
    rows = [row for row in PLAN["comparisons"] if row["comparison_id"] == comparison_id]
    if len(rows) != 1 or len(attempts) != 3:
        raise ValueError("exact three-case comparison required")
    cases = rows[0]["case_ids"]
    fixed = []
    postures = []
    for case_id, path in zip(cases, attempts):
        path = Path(path)
        config = json.loads((path / "config.json").read_text())
        if config["selected_case_id"] != case_id:
            raise ValueError("comparison source case mismatch")
        context = json.loads((path / "signal-context.json").read_text())
        measured = measure(case_id=case_id, context_path=path / "signal-context.json",
                           trace_path=path / "signal-readback.jsonl",
                           receipt_path=path / "signal-receipt.json",
                           allow_diagnostic=diagnostic)
        count = len(measured["observations"])
        if count != (9 if diagnostic else 900):
            raise ValueError("comparison source frame count mismatch")
        fixed.append({"kind": context["operator_vehicle_kind"],
                      "map": context["map_sha256"],
                      "roadway": context["roadway_polygon"],
                      "shoulder": context["shoulder_polygon"],
                      "route": context["right_turn_route"],
                      "controller": config["controller"],
                      "cameras": config["cameras"], "rate": config["rate_hz"],
                      "duration": config["duration_s"]})
        arm = measured["observations"][0]["right_arm"]
        postures.append({"case_id": case_id, "elbow_right_m": arm["elbow_right_m"],
                         "wrist_right_m": arm["wrist_right_m"],
                         "wrist_vertical_from_shoulder_m": arm["wrist_vertical_from_shoulder_m"]})
    if fixed[0] != fixed[1] or fixed[0] != fixed[2]:
        raise ValueError("comparison fixed condition changed")
    if len({(item["elbow_right_m"], item["wrist_right_m"],
             item["wrist_vertical_from_shoulder_m"]) for item in postures}) != 3:
        raise ValueError("comparison signal posture did not vary in original readback")
    return {"format": "worker-cycle-signal-comparison-audit",
            "comparison_id": comparison_id, "case_ids": cases,
            "source_kind": "diagnostic_fixture" if diagnostic else "original_saved_acquisition",
            "fixed_conditions_checked": sorted(fixed[0]),
            "measured_pose_differences": postures,
            "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--attempt", action="append", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(compare(args.comparison, args.attempt, args.diagnostic), sort_keys=True))


if __name__ == "__main__":
    main()
