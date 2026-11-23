"""Independently check fixed context and intended differences between saved cases.

This audit compares source-bound diagnostic or Native observations. It does not
decide whether either driver's conduct satisfied NRS 484B.560(3).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from native_scene import inspect
from saved_measurement import analyze, sha


def _same(left: object, right: object, name: str) -> None:
    if left != right:
        raise ValueError("comparison fixed condition differs: " + name)


def audit(comparison_id: str, left_attempt: Path, right_attempt: Path) -> dict:
    plan_path = Path(__file__).with_name("case-plan.json")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    comparison = next((c for c in plan["comparisons"]
                       if c["comparison_id"] == comparison_id), None)
    if comparison is None or len(comparison["case_ids"]) != 2:
        raise ValueError("unknown exact comparison")
    attempts = [Path(left_attempt).resolve(), Path(right_attempt).resolve()]
    packets, cases, reports, results = [], [], [], []
    for attempt, case_id in zip(attempts, comparison["case_ids"]):
        packet, case, _ = inspect(attempt / "site/packet.json", plan_path, case_id)
        report, result = analyze(attempt)
        if result["case_id"] != case_id:
            raise ValueError("comparison attempt selects another case")
        if json.loads((attempt / "analysis-report.json").read_text()) != report:
            raise ValueError("comparison saved report differs from original sources")
        if json.loads((attempt / "result.json").read_text()) != result:
            raise ValueError("comparison saved result differs from original sources")
        packets.append(packet)
        cases.append(case)
        reports.append(report)
        results.append(result)
    a, b = packets
    _same(a["sources"]["opendrive"]["sha256"],
          b["sources"]["opendrive"]["sha256"], "crossing map")
    _same(a["sources"]["crossing_authority"]["sha256"],
          b["sources"]["crossing_authority"]["sha256"], "crossing authority")
    for source in ("highway_boundary", "right_side_constraints", "camera_poses"):
        _same(a["sources"][source]["sha256"], b["sources"][source]["sha256"],
              source + " source")
    for key in ("sign_landmark_id", "rail_crossing_map_ref",
                "stopping_required_context", "stop_line_x_m", "rail_line_x_m",
                "approach_direction", "highway_right_y_m", "highway_left_y_m"):
        _same(a[key], b[key], key)
    _same(a["cameras"], b["cameras"], "camera plan")
    _same(results[0]["realized_observables"]["source_frame_count"],
          results[1]["realized_observables"]["source_frame_count"], "duration")
    if comparison_id == "two_marked_queue_arrangement":
        _same(a["sources"]["lane_markings"]["sha256"],
              b["sources"]["lane_markings"]["sha256"], "lane markings source")
        _same(a["marked_lanes"], b["marked_lanes"], "marked lanes")
        _same(a["rightmost_feasible_slot"], b["rightmost_feasible_slot"],
              "right-side feasibility")
        _same(a["ego_slot"], b["ego_slot"], "subject placement")
        if ([c["traffic_arrangement"] for c in cases] !=
                ["one_queue", "two_queues"] or
                results[0]["realized_observables"]["two_queue_aligned_frame_count"] != 0 or
                results[1]["realized_observables"]["two_queue_aligned_frame_count"] < 20):
            raise ValueError("queue contrast lacks original stopped arrangement")
        measured = {"aligned_frames": [r["realized_observables"]["two_queue_aligned_frame_count"]
                                       for r in results]}
    elif comparison_id in ("marked_lane_qualification", "marked_lane_above_boundary"):
        _same(a["rightmost_feasible_slot"], b["rightmost_feasible_slot"],
              "right-side feasibility")
        _same(a["ego_slot"], b["ego_slot"], "subject placement")
        _same(cases[0]["traffic_arrangement"], cases[1]["traffic_arrangement"],
              "traffic arrangement")
        expected = ([2, 4] if comparison_id == "marked_lane_qualification" else [4, 5])
        actual = [len(p["marked_lanes"]) for p in packets]
        if actual != expected or any(
                r["realized_observables"]["two_queue_aligned_frame_count"] < 20
                for r in results):
            raise ValueError("marked-lane contrast lacks measured source difference")
        measured = {"marked_highway_lane_counts": actual}
    elif comparison_id in ("four_marked_right_side", "two_marked_right_side"):
        _same(a["sources"]["lane_markings"]["sha256"],
              b["sources"]["lane_markings"]["sha256"], "lane markings source")
        _same(a["marked_lanes"], b["marked_lanes"], "marked lanes")
        _same(a["rightmost_feasible_slot"], b["rightmost_feasible_slot"],
              "right-side feasibility")
        _same(cases[0]["traffic_arrangement"], cases[1]["traffic_arrangement"],
              "traffic arrangement")
        offsets = [r["realized_observables"][
            "minimum_stopped_lateral_offset_from_reviewed_rightmost_m"] for r in results]
        if (a["ego_slot"] == b["ego_slot"] or offsets[0] is None or
                offsets[1] is None or offsets[1] <= offsets[0]):
            raise ValueError("right-side contrast lacks measured subject displacement")
        measured = {"stopped_offset_from_feasible_right_m": offsets}
    else:
        raise ValueError("comparison has no implemented measurement")
    return {"format": "c202480-independent-comparison-audit-v1",
            "comparison_id": comparison_id, "case_ids": comparison["case_ids"],
            "fixed_conditions": comparison["fixed_conditions"],
            "deliberate_differences": comparison["deliberate_differences"],
            "measured_difference": measured,
            "source_hashes": [{"site_packet_sha256": sha(p / "site/packet.json"),
                               "trace_sha256": sha(p / "trace.jsonl"),
                               "result_sha256": sha(p / "result.json"),
                               "analysis_report_sha256": sha(p / "analysis-report.json")}
                              for p in attempts],
            "physical_acceptance_claimed": False,
            "legal_judgment": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison-id", required=True)
    parser.add_argument("--left-attempt", required=True, type=Path)
    parser.add_argument("--right-attempt", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison_id, args.left_attempt,
                           args.right_attempt), indent=2))
