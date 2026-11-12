"""Independent saved-source comparison of the two selected alley stop cases."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from delivery_audit import (CAMERAS, check_access_review, check_native_boundary, check_pixel_review,
                            require, read, sha)


HERE = Path(__file__).resolve().parent
CHECKS = {"native_source", "all_participants", "time_join",
          "full_video_decode", "actual_pixels", "physical_completion"}
CASE_SUFFIXES = ("reference", "contrast")


def normalized_config(config: dict) -> dict:
    return {key: value for key, value in config.items() if key not in
            {"case_id", "case_suffix", "selected_case_id", "supported_case_ids", "case"}}


def normalized_native_context(context: dict) -> dict:
    """Only stop target and resulting route length may differ in Native setup."""
    return {key: value for key, value in context.items() if key not in
            {"case_id", "requested_stop_x_m", "requested_route_points"}}


def compare_fixed_inputs(reference: dict, contrast: dict) -> dict:
    """Compare source-shaped metadata without asserting any physical outcome."""
    a, b = reference["config"], contrast["config"]
    require(a["candidate_id"] == b["candidate_id"],
            "Comparison used different fallback/controller implementations")
    require(normalized_config(a) == normalized_config(b),
            "Undeclared camera, duration, law or controller config difference")
    require(reference["road_geometry"] == contrast["road_geometry"],
            "Fixed alley/access geometry differs")
    require(reference["runner_sha256"] == contrast["runner_sha256"],
            "Runner/weather request implementation differs")
    require(reference["native_context"].get("native_weather_readback") and
            reference["native_context"]["native_weather_readback"] ==
            contrast["native_context"].get("native_weather_readback"),
            "Fixed Native weather lacks matching original readback")
    require(normalized_native_context(reference["native_context"]) ==
            normalized_native_context(contrast["native_context"]),
            "Undeclared Native map, vehicle, spawn or controller difference")
    require(reference["native_context"]["requested_stop_x_m"] == -12.0 and
            contrast["native_context"]["requested_stop_x_m"] == 0.0,
            "Declared stop-station difference was not constructed")
    return {"candidate_id": a["candidate_id"],
            "held_conditions": ["cell", "actor", "legal context", "traffic controls",
                                "weather request", "other controller settings",
                                "camera and capture profile"],
            "declared_difference": "commanded_stop_station_m"}


def load_original(audit_path: Path, expected_case: str, *,
                  test_shape: bool = False) -> tuple[dict, dict]:
    audit = read(audit_path)
    require(audit.get("format") == "worker-delivery-audit" and
            audit.get("passed") is (not test_shape) and
            audit.get("case_id") == expected_case and
            (audit.get("source_shaped_unit_test") is True) == test_shape and
            CHECKS <= {key for key, value in audit.get("checks", {}).items() if value is True} and
            audit.get("legal_blocking_verdict_claimed") is False,
            "Comparison needs independent original delivery acceptance")
    auditor = Path(audit["auditor_path"]).resolve()
    require(auditor.name == "delivery_audit.py" and auditor.is_file() and
            sha(auditor) == audit.get("auditor_sha256") ==
            sha(HERE / "delivery_audit.py"),
            "Comparison delivery auditor revision changed")
    attempt = Path(audit["attempt_path"]).resolve()
    saved = Path(audit["saved_path"]).resolve()
    owner = Path(audit["owner_receipt_path"]).resolve()
    require(sha(owner) == audit["owner_receipt_sha256"],
            "Comparison owner release changed")
    boundary = check_native_boundary(attempt, saved, owner, expected_case,
                                    read(attempt / "capture-seal.json")
                                    ["native_revision"]["construction_sha256"],
                                    test_shape=test_shape)
    require(boundary["result_sha256"] == audit.get("source_result_sha256") and
            boundary["frame_map_sha256"] == audit.get("native_boundary", {})
            .get("frame_map_sha256") and
            sha(attempt / audit["video"]) == audit.get("video_sha256") and
            sha(attempt / audit["trace"]) == audit.get("trace_sha256"),
            "Comparison audit source binding changed")
    pixel = Path(audit["pixel_review_path"]).resolve()
    require(sha(pixel) == audit.get("pixel_review_sha256"),
            "Comparison actual-pixel review changed")
    check_pixel_review(pixel, expected_case, attempt,
                       attempt / audit["video"], test_shape=test_shape)
    access = Path(audit["access_review_path"]).resolve()
    require(sha(access) == audit.get("access_review_sha256") and
            check_access_review(access, expected_case, attempt,
                                test_shape=test_shape)
            ["property_access_id"] == audit.get("property_access_id"),
            "Comparison independent access review changed")
    from scenario_pipeline.worker_exchange.media import verify_receipt
    mapping_hash = sha(attempt / "video_frames.jsonl")
    primary_receipt = Path(audit["source_decode_receipt_path"]).resolve()
    require(sha(primary_receipt) == audit.get("source_decode_receipt_sha256"),
            "Comparison primary decode receipt changed")
    verify_receipt(attempt / audit["video"], primary_receipt, 480,
                   mapping_sha256=mapping_hash)
    camera_receipts = audit.get("source_camera_decode_receipts", {})
    require(set(camera_receipts) == set(CAMERAS),
            "Comparison source-camera decode receipts incomplete")
    for name in CAMERAS:
        receipt = Path(camera_receipts[name]["path"]).resolve()
        require(sha(receipt) == camera_receipts[name]["sha256"],
                "Comparison source-camera decode receipt changed")
        verify_receipt(attempt / (name + ".mkv"), receipt, 480,
                       mapping_sha256=mapping_hash)
    result = read(Path(read(saved / "processing.json")["result"]))
    return audit, {"attempt": attempt, "result": result,
                   "runner_sha256": read(attempt / "capture-seal.json")
                   ["native_revision"]["runner_sha256"],
                   "config": read(attempt / "config.json"),
                   "road_geometry": read(attempt / "road_geometry.json"),
                   "native_context": read(attempt / "native-construction-context.json")}


def audit_pair(reference_audit: Path, contrast_audit: Path, *,
               test_shape: bool = False) -> dict:
    plan = read(HERE / "case-plan.json")
    proposal = read(HERE / "proposals/cases.json")
    comparison = plan["comparisons"][0]
    expected = [HERE.name + "__" + suffix for suffix in CASE_SUFFIXES]
    require(comparison["case_ids"] == expected and
            comparison["deliberate_differences"] ==
            ["stopped_footprint_at_abutting_entrance"],
            "Frozen comparison changed")
    cases = {case["case_id"]: case for case in proposal["cases"]
             if case["target_type"] != "baseline"}
    require(set(cases) == set(expected), "Canonical selected case set differs")
    assignments = [cases[case]["variable_assignments"] for case in expected]
    require({key for key in assignments[0]
             if assignments[0][key] != assignments[1][key]} ==
            {"commanded_stop_station_m"},
            "Canonical pair changed an undeclared variable")
    audits, sources = zip(*(load_original(path, case, test_shape=test_shape) for path, case in
                            zip((reference_audit, contrast_audit), expected)))
    fixed = compare_fixed_inputs(*sources)
    require(audits[0].get("property_access_id") ==
            audits[1].get("property_access_id"),
            "Comparison used different abutting-property access contexts")
    measured = [source["result"].get("measured_values", {})
                .get("max_entrance_overlap_m") for source in sources]
    require(all(type(value) in (int, float) and math.isfinite(value)
                for value in measured) and
            abs(measured[0] - 0.0) <= .25 and
            abs(measured[1] - 5.2) <= .25 and measured[1] > measured[0],
            "Original stopped-footprint difference not measured as requested")
    return {"format": "c10014-independent-comparison-audit",
            "passed": not test_shape,
            "source_shaped_unit_test": test_shape,
            "comparison_id": comparison["comparison_id"],
            "case_ids": expected,
            "delivery_audit_sha256": [sha(reference_audit), sha(contrast_audit)],
            "native_result_sha256": [audit["source_result_sha256"] for audit in audits],
            "fixed_conditions": fixed["held_conditions"],
            "declared_difference": fixed["declared_difference"],
            "measured_overlap_m": measured,
            "legal_blocking_verdict_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-audit", type=Path, required=True)
    parser.add_argument("--contrast-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit_pair(args.reference_audit, args.contrast_audit)
    require(not args.output.exists(), "Retain previous comparison audit")
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
