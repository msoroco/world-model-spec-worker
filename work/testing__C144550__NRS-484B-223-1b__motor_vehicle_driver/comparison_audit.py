"""Independent saved-source audit of two conjunctive lane-change controls."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_construction import ASSIGNMENT


PAIRS = {
    "signal-prerequisite-control": ("both_observed", "signal_missing",
                                    "signal_precedes_center_departure",
                                    "driver_check_observed_before_departure"),
    "check-prerequisite-control": ("both_observed", "check_missing",
                                   "driver_check_observed_before_departure",
                                   "signal_precedes_center_departure")}
FIXED = ("reviewed_site_sha256", "source_lane_id", "destination_lane_id",
         "ego_blueprint", "target_vehicle_blueprint", "target_traffic_plan_sha256",
         "camera_plan_sha256", "capture_duration_s", "capture_rate_hz")


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
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--baseline-sha256", required=True)
    parser.add_argument("--contrast", required=True)
    parser.add_argument("--contrast-sha256", required=True)
    args = parser.parse_args()
    baseline, contrast, _, _ = PAIRS[args.comparison]
    print(json.dumps(audit(args.comparison, {
        baseline: _read_sealed(args.baseline, args.baseline_sha256),
        contrast: _read_sealed(args.contrast, args.contrast_sha256)}),
        indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
