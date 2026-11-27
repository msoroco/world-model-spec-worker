"""Independent original-only controlled contrasts for one-way roadway stops."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from stop_model import ASSIGNMENT


PAIRS = {
    "impediment_vs_passage": ("destination_follower_halts", "destination_follower_passes"),
    "safety_necessity": ("destination_follower_halts", "safety_conflict_stop"),
    "legal_direction": ("destination_follower_halts", "law_direction_stop"),
    "roadway_location": ("destination_follower_halts", "destination_off_roadway"),
    "complete_stop": ("destination_follower_halts", "destination_slow_roll"),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit_pair(comparison_id, reports):
    pair = PAIRS.get(comparison_id)
    require(pair is not None, "unknown roadway-stop comparison")
    ids = [ASSIGNMENT + "__" + name for name in pair]
    left, right = (reports.get(case_id) for case_id in ids)
    for case_id, report in zip(ids, (left, right)):
        require(isinstance(report, dict) and report.get("format") == "worker-delivery-audit" and
                report.get("passed") is True and report.get("protocol_fixture_checked") is False and
                report.get("case_id") == case_id and report.get("frame_count") == 900 and
                report.get("physical_acceptance_claimed") is True and
                report.get("comparison_record", {}).get("source_kind") == "original_native_capture",
                "original accepted stop report required: " + case_id)
    a, b = left["comparison_record"], right["comparison_record"]
    for key in ("fixed_source_sha256", "roadway_source_sha256", "shoulder_source_sha256",
                "camera_plan", "duration_s"):
        require(a.get(key) and a.get(key) == b.get(key),
                "changed fixed original stop condition: " + key)
    x, y = a["measurement"], b["measurement"]
    require(x.get("frame_count") == y.get("frame_count") == 900,
            "original stop measurement frame count differs")
    for measured in (x, y):
        require(measured.get("actual_complete_stop") in (True, False) and
                isinstance(measured.get("stop_surfaces"), list) and
                isinstance(measured.get("follower_progress_m"), (int, float)) and
                measured.get("follower_passed_ego") in (True, False),
                "original stop or follower movement missing")
        require(measured.get("statutory_verdict") is None and
                measured.get("normal_reasonable_movement_judgment") is None,
                "source audit must not issue a legal judgment")
    if comparison_id == "impediment_vs_passage":
        require(a["requested_surface"] == b["requested_surface"] == "roadway" and
                a["requested_reason"] == b["requested_reason"] == "destination" and
                a["requested_complete_stop"] is b["requested_complete_stop"] is True and
                a["requested_follower_action"] == "follow_and_halt" and
                b["requested_follower_action"] == "pass" and
                x["follower_passed_ego"] is False and y["follower_passed_ego"] is True,
                "follower passage contrast not measured")
        require(a["passing_space_source_sha256"] == b["passing_space_source_sha256"],
                "passing geometry changed instead of follower action")
    elif comparison_id == "safety_necessity":
        require(a["requested_reason"] == "destination" and
                b["requested_reason"] == "safety_conflict" and
                a["requested_surface"] == b["requested_surface"] == "roadway" and
                x["actual_complete_stop"] is y["actual_complete_stop"] is True and
                all(item is None for item in x["collision_or_conflict"]) and
                any(item is not None for item in y["collision_or_conflict"]) and
                a["conflict_source_sha256"] != b["conflict_source_sha256"],
                "source-backed safety conflict contrast not measured")
    elif comparison_id == "legal_direction":
        require(a["requested_reason"] == "destination" and
                b["requested_reason"] == "official_direction" and
                a["requested_surface"] == b["requested_surface"] == "roadway" and
                x["actual_complete_stop"] is y["actual_complete_stop"] is True and
                all(item is None for item in x["official_direction_readback"]) and
                any(item is not None for item in y["official_direction_readback"]) and
                a["direction_source_sha256"] != b["direction_source_sha256"],
                "source-backed lawful-direction contrast not measured")
    elif comparison_id == "roadway_location":
        require(a["requested_surface"] == "roadway" and
                b["requested_surface"] == "shoulder" and
                a["requested_reason"] == b["requested_reason"] == "destination" and
                x["stop_surfaces"] == ["roadway"] and y["stop_surfaces"] == ["shoulder"] and
                a["passing_space_source_sha256"] == b["passing_space_source_sha256"],
                "roadway-versus-shoulder footprint contrast not measured")
    else:
        require(a["requested_complete_stop"] is True and
                b["requested_complete_stop"] is False and
                a["requested_surface"] == b["requested_surface"] == "roadway" and
                x["actual_complete_stop"] is True and y["actual_complete_stop"] is False,
                "complete-stop versus slow-roll contrast not measured")
    return {"format": "c150640-roadway-stop-independent-comparison-v1",
            "comparison_id": comparison_id, "case_ids": ids,
            "fixed_source_sha256": a["fixed_source_sha256"],
            "physical_comparison_passed": True,
            "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-map", type=Path, required=True)
    parser.add_argument("--comparison", choices=tuple(PAIRS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = json.loads(args.report_map.read_text(encoding="utf-8"))
    reports = {case_id: json.loads(Path(path).read_text(encoding="utf-8"))
               for case_id, path in paths.items()}
    result = audit_pair(args.comparison, reports)
    if args.output.exists():
        raise ValueError("refusing to overwrite comparison audit")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
