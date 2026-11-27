"""Independent saved-source audit of two conjunctive lane-change controls."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from camera_capture import SIZES
from analysis import build_report
from delivery_audit import audit as audit_delivery
from native_construction import ASSIGNMENT


PAIRS = {
    "signal-prerequisite-control": ("both_observed", "signal_missing",
                                    "signal_precedes_center_departure",
                                    "driver_check_observed_before_departure"),
    "check-prerequisite-control": ("both_observed", "check_missing",
                                   "driver_check_observed_before_departure",
                                   "signal_precedes_center_departure"),
    "accepted-source-1-signal-control": ("accepted_source_1", "signal_missing",
                                         "signal_precedes_center_departure",
                                         "driver_check_observed_before_departure"),
    "accepted-source-2-check-control": ("accepted_source_2", "check_missing",
                                        "driver_check_observed_before_departure",
                                        "signal_precedes_center_departure"),
    "accepted-source-3-signal-control": ("accepted_source_3", "signal_missing",
                                         "signal_precedes_center_departure",
                                         "driver_check_observed_before_departure")}
FIXED = ("reviewed_site_sha256", "source_lane_id", "destination_lane_id",
         "ego_blueprint", "target_vehicle_blueprint", "target_traffic_plan_sha256",
         "camera_plan_sha256", "capture_duration_s", "capture_rate_hz")
REQUIRED_SOURCES = ("lane-change-capture-receipt.json", "readback-inventory.json",
                    "frame_map.json", "ego_pose.json", "native_signal.json",
                    "driver_check.json", "original-driver-input.jsonl",
                    "target-traffic-history.jsonl",
                    "original-camera-frames/camera-manifest.json", "reviewed-site.json")


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _production_report(attempt, case, owner_receipt):
    if not owner_receipt:
        raise ValueError("original owner-release receipt required for comparison")
    root = Path(attempt).resolve()
    delivery = audit_delivery(root, case, owner_receipt=owner_receipt)
    if delivery.get("format") != "worker-delivery-audit" or delivery.get("passed") is not True:
        raise ValueError("original Native delivery audit required for comparison")
    report = json.loads((root / "analysis-report.json").read_text())
    hashes = report.get("original_source_hashes", {})
    if not set(REQUIRED_SOURCES) <= set(hashes):
        raise ValueError("saved comparison report omits required original sources")
    for name in REQUIRED_SOURCES:
        path = root / name
        if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != hashes[name]:
            raise ValueError("saved comparison original source missing or changed: " + name)
    site_path = root / "reviewed-site.json"
    site = json.loads(site_path.read_text())
    config = json.loads((root / "config.json").read_text())
    expected = {"reviewed_site_sha256": hashes["reviewed-site.json"],
                "source_lane_id": site["lanes"]["source"]["lane_id"],
                "destination_lane_id": site["lanes"]["destination"]["lane_id"],
                "ego_blueprint": site["ego_blueprint"],
                "target_vehicle_blueprint": site["target_vehicle_blueprint"],
                "target_traffic_plan_sha256": _digest({
                    "spawn": site["target_spawn_xyz_yaw"],
                    "route": site["lanes"]["destination"]["centerline_world_xyz_m"]}),
                "camera_plan_sha256": _digest({
                    "poses": site["camera_poses_xyz_pitch_yaw"], "sizes": SIZES}),
                "capture_duration_s": config["duration_s"],
                "capture_rate_hz": config["rate_hz"]}
    if report.get("fixed_context") != expected:
        raise ValueError("saved comparison fixed context differs from original sources")
    recomputed = build_report(root)
    for field in ("case_id", "fixed_context", "measurements", "original_source_hashes"):
        if report.get(field) != recomputed.get(field):
            raise ValueError("saved comparison measurement differs from original source recomputation: " + field)
    return report


def audit_original_attempts(comparison_id, attempts, owner_receipts):
    if comparison_id not in PAIRS:
        raise ValueError("unknown declared lane-change comparison")
    baseline, contrast, _, _ = PAIRS[comparison_id]
    if set(attempts) != {baseline, contrast} or set(owner_receipts) != set(attempts):
        raise ValueError("exact original attempt and owner receipt pairs required")
    reports = {variant: _production_report(attempts[variant], ASSIGNMENT + "__" + variant,
                                           owner_receipts[variant]) for variant in attempts}
    result = audit(comparison_id, reports)
    result["production_original_attempts_audited"] = True
    result["original_attempts"] = {variant: str(Path(attempts[variant]).resolve())
                                   for variant in attempts}
    return result


def _read_sealed(path, sha256):
    path = Path(path)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError("saved comparison report SHA256 differs")
    return json.loads(raw)


def audit(comparison_id, reports):
    if comparison_id not in PAIRS:
        raise ValueError("unknown declared lane-change comparison")
    baseline, contrast, changed, held = PAIRS[comparison_id]
    if set(reports) != {baseline, contrast}:
        raise ValueError("exact declared comparison members required")
    first, second = reports[baseline], reports[contrast]
    for variant, report in ((baseline, first), (contrast, second)):
        if report.get("case_id") != ASSIGNMENT + "__" + variant:
            raise ValueError("saved comparison case identity differs")
        if report.get("format") != "c144550-saved-lane-change-report-v1":
            raise ValueError("saved comparison measurement report required")
        if not report.get("original_source_hashes") or report.get("legal_verdict_claimed") is not False:
            raise ValueError("source-bound nonlegal comparison report required")
        if any(not report.get("fixed_context", {}).get(key) for key in FIXED):
            raise ValueError("fixed comparison context source missing")
        measured = report.get("measurements", {})
        if any(type(measured.get(key)) is not bool for key in (changed, held)):
            raise ValueError("two independent conjunct measurements required")
    if any(first["fixed_context"][key] != second["fixed_context"][key] for key in FIXED):
        raise ValueError("declared fixed lane-change conditions differ")
    if first["measurements"][held] is not True or second["measurements"][held] is not True:
        raise ValueError("held conjunct was not observed in both members")
    if first["measurements"][changed] is not True or second["measurements"][changed] is not False:
        raise ValueError("declared conjunct difference not observed")
    return {"format": "c144550-independent-comparison-audit-v1",
            "comparison_id": comparison_id, "passed": True,
            "case_ids": [first["case_id"], second["case_id"]],
            "fixed_context": {key: first["fixed_context"][key] for key in FIXED},
            "declared_measured_difference": changed,
            "held_measured_conjunct": held,
            "physical_safety_or_legal_judgment_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--baseline")
    parser.add_argument("--baseline-sha256")
    parser.add_argument("--contrast")
    parser.add_argument("--contrast-sha256")
    parser.add_argument("--baseline-attempt")
    parser.add_argument("--baseline-owner-release-receipt")
    parser.add_argument("--contrast-attempt")
    parser.add_argument("--contrast-owner-release-receipt")
    args = parser.parse_args()
    baseline, contrast, _, _ = PAIRS[args.comparison]
    if all((args.baseline_attempt, args.baseline_owner_release_receipt,
            args.contrast_attempt, args.contrast_owner_release_receipt)):
        result = audit_original_attempts(args.comparison,
            {baseline: args.baseline_attempt, contrast: args.contrast_attempt},
            {baseline: args.baseline_owner_release_receipt,
             contrast: args.contrast_owner_release_receipt})
    elif all((args.baseline, args.baseline_sha256, args.contrast, args.contrast_sha256)):
        result = audit(args.comparison, {
            baseline: _read_sealed(args.baseline, args.baseline_sha256),
            contrast: _read_sealed(args.contrast, args.contrast_sha256)})
        result["production_original_attempts_audited"] = False
    else:
        parser.error("supply both original attempts and owner receipts, or both sealed reports")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
