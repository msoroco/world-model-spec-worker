"""Independent original-source comparison for the selected crosswalk pair.

The measured lateral separation is an engineering observation, not a legal
practicability cutoff. Source-shaped unit data never yields a passing receipt.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from delivery_audit import audit as delivery_audit, read, require, sha


HERE = Path(__file__).resolve().parent
CASE_IDS = (HERE.name + "__reference", HERE.name + "__contrast")
CHECKS = {"native_source", "all_participants", "time_join",
          "full_video_decode", "actual_pixels", "physical_completion"}


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def normalized_config(config: dict) -> dict:
    return {key: value for key, value in config.items() if key not in
            {"case", "case_id", "case_suffix", "selected_case_id"}}


def normalized_native_context(context: dict) -> dict:
    result = {key: value for key, value in context.items() if key not in
              {"case_id", "initial_original_footprint", "requested_plan"}}
    plan = context.get("requested_plan", {})
    result["requested_plan"] = {key: value for key, value in plan.items()
                                if key not in {"case_id", "engineering"}}
    engineering = plan.get("engineering", {})
    result["requested_engineering"] = {
        key: value for key, value in engineering.items()
        if key != "target_lateral_m"}
    return result


def load_original(path: Path, case_id: str, *, test_shape: bool = False) -> tuple[dict, dict]:
    """Recheck the current independent delivery auditor and its exact sources."""
    receipt = read(path)
    require(receipt.get("format") == "worker-delivery-audit" and
            receipt.get("case_id") == case_id and
            receipt.get("passed") is (not test_shape) and
            (receipt.get("source_shaped_unit_test") is True) == test_shape and
            CHECKS <= {name for name, passed in receipt.get("checks", {}).items()
                       if passed is True} and
            receipt.get("legal_verdict_claimed") is False and
            receipt.get("practicability_judgment") == "unverified",
            "Comparison requires independent original delivery acceptance")
    auditor = Path(receipt.get("auditor_path", "")).resolve()
    require(auditor == (HERE / "delivery_audit.py").resolve() and
            receipt.get("auditor_sha256") == sha(auditor),
            "Comparison delivery auditor revision changed")
    attempt = Path(receipt["attempt_path"]).resolve()
    saved = Path(receipt["saved_path"]).resolve()
    owner = Path(receipt["owner_receipt_path"]).resolve()
    require(owner.is_file() and sha(owner) == receipt.get("owner_receipt_sha256"),
            "Comparison owner release changed")
    seal = read(attempt / "capture-seal.json")
    construction = seal["native_revision"]["construction_sha256"]
    pixel = Path(receipt["pixel_review_path"]).resolve()
    crossing = Path(receipt["crossing_review_path"]).resolve()
    primary = (attempt / receipt["video"]).resolve()
    core = (attempt / receipt["trace"]).resolve()
    decode_dir = Path(receipt["source_decode_receipt_path"]).resolve().parent
    require(sha(pixel) == receipt.get("pixel_review_sha256") and
            sha(crossing) == receipt.get("crossing_review_sha256") and
            sha(primary) == receipt.get("video_sha256") and
            sha(core) == receipt.get("trace_sha256"),
            "Comparison reviewed source changed")
    current = delivery_audit(attempt, saved, owner, case_id, construction,
                             pixel, crossing, primary, core, decode_dir,
                             test_shape=test_shape)
    require(current.get("source_result_sha256") ==
                receipt.get("source_result_sha256") and
            current.get("motion_status") == receipt.get("motion_status") and
            current.get("lifecycle_capture_seal_sha256") ==
                receipt.get("lifecycle_capture_seal_sha256") and
            current.get("source_decode_receipt_sha256") ==
                receipt.get("source_decode_receipt_sha256"),
            "Comparison delivery source binding changed")
    return receipt, {"attempt": attempt,
                     "config": read(attempt / "config.json"),
                     "native_context": read(attempt / "native-construction-context.json"),
                     "crosswalk_context": read(attempt / "crosswalk-context.json"),
                     "crossing_review": read(crossing),
                     "samples": rows(attempt / "native_samples.jsonl"),
                     "result": read(Path(read(saved / "processing.json")["result"]))}


def compare_fixed(reference: dict, contrast: dict) -> dict:
    """Compare requested controls and measured paths from two original sources."""
    a, b = reference, contrast
    require(a["config"].get("candidate_id") == b["config"].get("candidate_id") and
            normalized_config(a["config"]) == normalized_config(b["config"]),
            "Undeclared camera, duration, law or controller difference")
    require(a["crosswalk_context"] == b["crosswalk_context"] and
            normalized_native_context(a["native_context"]) ==
                normalized_native_context(b["native_context"]),
            "Fixed Native map, actor, route or crossing context differs")
    requested = [source["native_context"]["requested_plan"]["engineering"]
                 ["target_lateral_m"] for source in (a, b)]
    require(requested == [-0.65, 0.65],
            "Declared 1.3 m lateral path difference was not constructed")
    reviews = [source["crossing_review"] for source in (a, b)]
    require(all(review.get("marked_highway_crosswalk_confirmed") is True and
                review.get("alley_route_connection_confirmed") is True and
                review.get("practicability_judgment") == "unverified"
                for review in reviews) and
            {name: item.get("observation") for name, item in
             reviews[0].get("facts", {}).items()} ==
            {name: item.get("observation") for name, item in
             reviews[1].get("facts", {}).items()},
            "Fixed passage, signal, obstacle or pedestrian context differs")
    samples = [source["samples"] for source in (a, b)]
    require(all(len(stream) == 240 for stream in samples),
            "Comparison lacks full original Native sample windows")
    for index, (ref, con) in enumerate(zip(*samples)):
        require(all(type(row.get("native_frame")) is int and
                    type(row.get("time_s")) in (int, float) and
                    math.isfinite(row["time_s"]) and
                    abs(row["time_s"] - index / 20) <= 0.1
                    for row in (ref, con)) and
                ref.get("crosswalk_id") == con.get("crosswalk_id") ==
                    a["crosswalk_context"]["crosswalk_id"],
                "Comparison original time or crosswalk join differs")
    deltas = [con["pedestrian_xy_m"][1] - ref["pedestrian_xy_m"][1]
              for ref, con in zip(*samples)]
    require(all(type(value) in (int, float) and math.isfinite(value)
                for value in deltas),
            "Comparison original lateral position missing")
    observed = sum(deltas) / len(deltas)
    require(abs(observed - 1.3) <= 0.2 and
            all(abs(value - 1.3) <= 0.35 for value in deltas),
            "Original measured lateral difference differs from requested path")
    values = [source["result"].get("measured_values", {})
              .get("observed_crosswalk_half") for source in (a, b)]
    require(values == ["right", "left"],
            "Original measured right/left crossing pair differs")
    return {"candidate_id": a["config"]["candidate_id"],
            "held_conditions": ["cell", "actor", "law", "map", "crosswalk",
                                "signals", "passage space", "obstacles",
                                "other pedestrians", "controller", "cameras",
                                "capture interval"],
            "declared_difference": "pedestrian_lateral_crosswalk_half",
            "requested_lateral_offsets_m": requested,
            "observed_mean_lateral_separation_m": observed,
            "observed_min_lateral_separation_m": min(deltas),
            "observed_max_lateral_separation_m": max(deltas),
            "engineering_tolerance_m": 0.2,
            "legal_practicability_threshold_claimed": False}


def audit_pair(reference_audit: Path, contrast_audit: Path, *,
               test_shape: bool = False) -> dict:
    plan = read(HERE / "case-plan.json")["comparisons"][0]
    require(plan.get("case_ids") == list(CASE_IDS) and
            plan.get("deliberate_differences") ==
                ["pedestrian_lateral_crosswalk_half"],
            "Selected comparison changed from source-reviewed plan")
    receipts, sources = zip(*(load_original(path, case, test_shape=test_shape)
                              for path, case in zip((reference_audit,
                                                     contrast_audit), CASE_IDS)))
    fixed = compare_fixed(*sources)
    return {"format": "c10316-independent-comparison-audit-v1",
            "passed": not test_shape, "source_shaped_unit_test": test_shape,
            "comparison_id": plan["comparison_id"],
            "case_ids": list(CASE_IDS),
            "delivery_audit_sha256": [sha(reference_audit), sha(contrast_audit)],
            "native_result_sha256": [receipt["source_result_sha256"]
                                     for receipt in receipts],
            **fixed, "legal_verdict_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-audit", type=Path, required=True)
    parser.add_argument("--contrast-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_pair(args.reference_audit, args.contrast_audit)
    require(not args.output.exists(), "Retain previous comparison audit")
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
