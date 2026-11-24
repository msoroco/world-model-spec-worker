"""Independent saved-source comparison with explicit diagnostic fixture mode.

The selected delivery implementation remains saved_comparison_audit.py and
requires original sources. This helper measures synthetic compatibility pairs.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from crosswalk_measurements import ASSIGNMENT_ID, measure
from saved_video_audit import audit as audit_video


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _close_xy(left, right, tolerance_m: float = 0.25) -> bool:
    if not all(isinstance(value, list) and len(value) == 2 and all(
        type(part) in (int, float) and math.isfinite(part) for part in value
    ) for value in (left, right)):
        raise ValueError("finite original comparison centers required")
    return math.dist(left, right) <= tolerance_m


def _recompute(root: Path, case_id: str,
               fixture_mode: bool = False) -> tuple[dict, dict, dict, list[dict]]:
    measured = measure(case_id=case_id, context_path=root / "context.json",
                       trace_path=root / "trace.jsonl", receipt_path=root / "receipt.json",
                       fixture_mode=fixture_mode)
    media = audit_video(directory=root, case_id=case_id, fixture_mode=fixture_mode)
    context = json.loads((root / "context.json").read_text(encoding="utf-8"))
    trace = _rows(root / "trace.jsonl")
    return measured, media, context, trace


def audit(*, left_dir: str | Path, right_dir: str | Path,
          comparison_id: str, plan_path: str | Path | None = None,
          fixture_mode: bool = False) -> dict:
    if plan_path is None:
        plan_path = Path(__file__).with_name("case-plan.json")
    plan_raw = Path(plan_path).read_bytes()
    plan = json.loads(plan_raw)
    if plan.get("assignment_id") != ASSIGNMENT_ID:
        raise ValueError("exact assignment comparison plan required")
    pairs = {row["comparison_id"]: row["case_ids"] for row in plan.get("comparisons", [])}
    if comparison_id not in pairs:
        raise ValueError("unknown exact crosswalk comparison")
    roots = [Path(left_dir), Path(right_dir)]
    reports = []
    recomputed = []
    for root, case_id in zip(roots, pairs[comparison_id]):
        path = root / "crosswalk-measurement.json"
        if path.is_symlink() or not path.is_file():
            raise ValueError("saved original measurement missing")
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("assignment_id") != ASSIGNMENT_ID or report.get("case_id") != case_id:
            raise ValueError("saved report exact case differs")
        if report.get("physical_acceptance") != "unverified" or report.get("legal_verdict_claimed") is not False:
            raise ValueError("saved report asserts unsupported physical or legal acceptance")
        if report.get("diagnostic_fixture") is not fixture_mode:
            raise ValueError("saved report provenance differs")
        measured, media, context, trace = _recompute(root, case_id, fixture_mode)
        if report.get("measured_values") != measured or report.get("media") != media:
            raise ValueError("saved report differs from original source recomputation")
        expected_observed = {
            "rear_approach_sampled": bool(measured["rear_approach_frames"]),
            "lead_stop_sampled": bool(measured["lead_stopped_frames"]),
            "pedestrian_in_polygon_sampled": bool(measured["pedestrian_crosswalk_frames"]),
            "ego_full_pass_sampled": bool(measured["ego_ahead_frames"]),
        }
        if report.get("observed") != expected_observed:
            raise ValueError("saved observed flags differ from original source recomputation")
        current_hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                          for name in ("context.json", "trace.jsonl", "frame-map.jsonl", "receipt.json")}
        if report.get("source_sha256") != current_hashes:
            raise ValueError("saved report original source hash differs")
        reports.append((path, report))
        recomputed.append((measured, media, context, trace))
    left, right = recomputed
    left_measure, left_media, left_context, left_trace = left
    right_measure, right_media, right_context, right_trace = right
    for key in ("map_sha256", "junction_kind", "layout", "road_axis"):
        if left_context.get(key) != right_context.get(key):
            raise ValueError("comparison changed fixed original " + key)
    if left_measure["frame_count"] != 900 or right_measure["frame_count"] != 900:
        raise ValueError("comparison lacks complete original 45-second captures")
    if len(left_trace) != len(right_trace) or any(
        not _close_xy(a.get("lead_center"), b.get("lead_center")) or
        not _close_xy(a.get("pedestrian_center"), b.get("pedestrian_center"))
        for a, b in zip(left_trace, right_trace)
    ):
        raise ValueError("comparison changed fixed lead or pedestrian trajectory")
    for name in left_media["videos"]:
        if left_media["videos"][name]["frames"] != right_media["videos"][name]["frames"]:
            raise ValueError("comparison changed camera duration")
    changed = {"crosswalk_kind": left_measure["crosswalk_kind"] != right_measure["crosswalk_kind"],
               "lead_stop_purpose": left_measure["stopped_vehicle_purpose_claim"] != right_measure["stopped_vehicle_purpose_claim"],
               "ego_full_pass": bool(left_measure["ego_ahead_frames"]) != bool(right_measure["ego_ahead_frames"])}
    requested = "crosswalk_kind" if comparison_id == "crosswalk_kind" else (
        "lead_stop_purpose" if comparison_id == "stop_purpose" else "ego_full_pass"
    )
    if not changed[requested] or any(value for key, value in changed.items() if key != requested):
        raise ValueError("comparison observed difference differs from declared variable")
    if comparison_id != "crosswalk_kind" and left_context["crosswalk"] != right_context["crosswalk"]:
        raise ValueError("comparison changed fixed crosswalk geometry")
    if comparison_id != "stop_purpose" and left_context["stopped_vehicle_purpose"] != right_context["stopped_vehicle_purpose"]:
        raise ValueError("comparison changed fixed lead stop purpose source")
    return {"comparison_id": comparison_id, "case_ids": pairs[comparison_id],
            "diagnostic_fixture": fixture_mode,
            "plan_sha256": hashlib.sha256(plan_raw).hexdigest(),
            "saved_report_sha256": [hashlib.sha256(path.read_bytes()).hexdigest() for path, _ in reports],
            "declared_difference": requested, "measured_difference": changed,
            "fixed_source_conditions_checked": ["map_sha256", "junction_kind", "layout",
                                                "road_axis", "lead_trajectory", "pedestrian_trajectory",
                                                "camera_duration"],
            "physical_acceptance": "unverified", "legal_judgment": "unresolved"}
