"""Independent CPU audit of the C111088 straight/yield diagnostic pair.

This audits retained saved-processing results and exact construction identity.
It makes no Native, pixel, right-of-way, or physical acceptance claim.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent


def load(path: Path):
    return json.loads(path.read_text())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str):
    if not condition:
        raise ValueError(message)


def audit(saved_overrides: dict[str, dict] | None = None) -> dict:
    manifest_path = PACKAGE / "execution-manifest.json"
    manifest = load(manifest_path)
    require(len(manifest["cases"]) == 2, "Comparison needs exactly two cases")
    require({c["case_id"].rsplit("__", 1)[-1] for c in manifest["cases"]} == {"false", "true"},
            "Comparison cases differ")
    construction_by_suffix = {}
    case_results = {}
    for case in manifest["cases"]:
        suffix = case["case_id"].rsplit("__", 1)[-1]
        construction_path = PACKAGE / case["construction"]
        require(digest(construction_path) == case["construction_sha256"],
                "Construction hash differs: " + suffix)
        construction = load(construction_path)
        require(construction["case_id"] == case["case_id"], "Construction case mismatch")
        config = next((json.loads(f["content"]) for f in construction["files"]
                       if f["path"] == "config.json"), None)
        require(config is not None, "Inline configuration missing")
        construction_by_suffix[suffix] = config

        saved_path = PACKAGE / f"current-v4-{suffix}-primary-saved-processing.json"
        saved = (saved_overrides or {}).get(suffix, load(saved_path))
        require(saved["case_id"] == case["case_id"] and saved["candidate_id"] == "primary",
                "Saved receipt case/candidate mismatch")
        require(saved["passed"] is True and saved["recorded_only"] is True and
                saved["originals_preserved"] is True,
                "Saved processing or source preservation failed")
        require(saved["physical_acceptance_claimed"] is False and
                saved["legal_acceptance_claimed"] is False,
                "Saved receipt overclaims acceptance")
        result_path = Path(saved["result"])
        require(result_path.is_file() and digest(result_path) == saved["result_sha256"],
                "Saved result missing or changed")
        result = load(result_path)
        require(result["case_id"] == case["case_id"] and result["accepted"] is False and
                result["legal_verdict_claimed"] is False,
                "Saved result identity or acceptance differs")
        measurements = result["measured_values"]
        require(measurements["original_joins"]["frames"] == 840,
                "Saved result lacks full 840-frame join")
        require(measurements["pixel_review"]["diagnostic_only"] is True and
                measurements["pixel_review"]["original_pixel_reviewed"] is False,
                "Synthetic aspect disclosure differs")
        measure = measurements["straight_arrow_and_yield"]
        require(measure["straight_heading_no_turn_observed"] is True and
                not measure["heading_deviation_frames"] and
                measure["legal_verdict_claimed"] is False,
                "Straight-travel measurement differs")
        case_results[suffix] = {
            "case_id": case["case_id"], "saved_receipt_sha256": digest(saved_path),
            "saved_result_sha256": digest(result_path),
            "source_sha256": measurements["original_joins"]["source_sha256"],
            "crossing_frame": measure["first_front_stop_line_crossing_frame"],
            "last_other_occupancy_frame": measure["last_other_vehicle_occupancy_under_verified_arrow_frame"],
            "other_vehicle_present": measure["other_vehicle_present_under_verified_arrow"],
            "yielded_before_entry": measure["yielded_before_entry"],
        }

    false_config = construction_by_suffix["false"].copy()
    true_config = construction_by_suffix["true"].copy()
    for key in ("case", "case_id", "selected_case_id", "lawful_conflict_participant_present"):
        false_config.pop(key, None)
        true_config.pop(key, None)
    require(false_config == true_config, "Uncontrolled configuration change")
    require(construction_by_suffix["false"]["lawful_conflict_participant_present"] is False and
            construction_by_suffix["true"]["lawful_conflict_participant_present"] is True,
            "Comparison variable is not isolated")
    absent, present = case_results["false"], case_results["true"]
    require(absent["other_vehicle_present"] is False and
            absent["last_other_occupancy_frame"] is None and
            present["other_vehicle_present"] is True and
            isinstance(present["last_other_occupancy_frame"], int),
            "Synthetic conflict contrast differs")
    require(present["yielded_before_entry"] is True and
            present["crossing_frame"] > present["last_other_occupancy_frame"],
            "Synthetic yield timing differs")
    require(absent["source_sha256"]["native_samples.jsonl"] !=
            present["source_sha256"]["native_samples.jsonl"],
            "Distinct Native sample sources required")
    return {
        "format": "c111088-independent-straight-yield-comparison-v1",
        "passed": True, "manifest_sha256": digest(manifest_path),
        "comparison_variable": "lawful_conflict_participant_present",
        "fixed_configuration_isolated": True,
        "cases": case_results,
        "scope": "synthetic CPU diagnostic; no original Native, source-pixel, lawful-entry, physical, or legal acceptance",
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
