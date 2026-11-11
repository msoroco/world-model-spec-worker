"""Independent source-bound comparison of unselected saved CPU diagnostics.

This deliberately does not decide physical completion, district applicability, or
delivery acceptance. Original captures require a separate acceptance audit.
"""
import argparse
import hashlib
import json
from pathlib import Path


CASES = {
    "intersection": ("reference", "contrast"),
    "divided_opening": ("divided_reference", "divided_opening"),
}
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
FIXED = ("assignment_id", "assignment_sha256", "cell_id", "law_id", "actor",
         "ego_blueprint", "source_text", "frames", "rate_hz", "duration_s",
         "cameras", "camera_policy", "requested_approach_speed_mps",
         "pre_turn_dwell_s", "candidate_id")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    path = Path(path)
    require(path.is_file(), "Missing comparison source: " + str(path))
    return json.loads(path.read_text())


def side(receipt_path, suffix, candidate):
    receipt_path = Path(receipt_path)
    receipt = load(receipt_path)
    require(receipt.get("passed") is True and receipt.get("recorded_only") is True,
            "Saved processing receipt did not pass")
    require(receipt.get("candidate_id") == candidate and
            receipt.get("case_id", "").endswith("__" + suffix),
            "Saved processing identity differs")
    analysis = Path(receipt["analysis_directory"])
    require(analysis.is_dir(), "Missing saved analysis directory")
    require(analysis.resolve() == (Path(receipt["version"]) / "analysis").resolve(),
            "Saved analysis escapes the retained version")
    originals = receipt.get("original_source_hashes", {})
    files = ("config.json", "construction.json", "result.json", "analysis-report.json",
             "raw.json", "road.xodr", "road-context.json", "frontage-plan.json",
             "frontage-context.json", "requested-tracks.jsonl", "request-context.json",
             "trace.jsonl", "video_frames.jsonl") + tuple(name + ".mkv" for name in CAMERAS)
    for name in files:
        require(name in originals and sha(analysis/name) == originals[name],
                "Missing or stale saved source: " + name)
    require(sha(analysis/"result.json") == receipt["result_sha256"],
            "Saved result receipt hash differs")
    require(receipt.get("native_revision", {}).get("construction_sha256") ==
            receipt.get("analysis_revision", {}).get("construction_sha256") ==
            sha(analysis/"construction.json"),
            "Saved construction revision differs")
    config, result = load(analysis/"config.json"), load(analysis/"result.json")
    report = load(analysis/"analysis-report.json")
    require(config["case_id"] == receipt["case_id"] == result["case_id"] == report["case_id"]
            and config["candidate_id"] == report["candidate_id"] == candidate,
            "Saved case or candidate identity differs")
    require(config["frames"] == 800 and config["rate_hz"] == 20 and
            tuple(config["cameras"]) == CAMERAS and config["duration_s"] == 40,
            "Capture profile differs")
    require(receipt.get("timestamp_joins", {}).get("frames") == 800 and
            receipt["timestamp_joins"].get("passed") is True and
            receipt.get("originals_preserved") is True,
            "Saved original/frame join unproved")
    decode = receipt.get("final_video_checks", {})
    require(decode.get("passed") is True and decode.get("frames") == 800 and
            decode.get("format") == "source-decode", "Saved final video decode unproved")
    for context, source, key in (("road-context.json", "road.xodr", "authored_road"),
                                 ("frontage-context.json", "frontage-plan.json", "authored_frontage"),
                                 ("request-context.json", "requested-tracks.jsonl", "authored_request")):
        binding = load(analysis/context)[key]
        require(binding == {"source": source, "sha256": originals[source]},
                "Source context binding differs: " + context)
    require(config["road_sha256"] == originals["road.xodr"] and
            config["tracks_sha256"] == originals["requested-tracks.jsonl"],
            "Request source hash differs")
    require(report.get("physical_acceptance_claimed") is False and
            report.get("legal_verdict_claimed") is False and
            result.get("provenance_kind") == "synthetic_local_diagnostic" and
            result.get("accepted") is False,
            "Diagnostic evidence was presented as accepted or original")
    checks = result.get("target_checks", [])
    require(len(checks) == 1 and checks[0].get("matched") is True and
            checks[0].get("physical_cause_confirmed") is False,
            "Diagnostic target check differs")
    return {"receipt_path": str(receipt_path), "receipt_sha256": sha(receipt_path),
            "analysis": analysis, "config": config, "result": result,
            "road_sha256": originals["road.xodr"],
            "frontage_sha256": originals["frontage-plan.json"]}


def audit(reference_receipt, contrast_receipt, branch, candidate):
    require(branch in CASES, "Unknown comparison branch")
    left = side(reference_receipt, CASES[branch][0], candidate)
    right = side(contrast_receipt, CASES[branch][1], candidate)
    a, b = left["config"], right["config"]
    for key in FIXED:
        require(a.get(key) == b.get(key), "Fixed comparison condition differs: " + key)
    require(left["road_sha256"] == right["road_sha256"] and
            left["frontage_sha256"] == right["frontage_sha256"],
            "Fixed road or frontage source differs")
    require(a["requested_turn_center_x_m"] == -45.0 and
            b["requested_turn_center_x_m"] == 0.0,
            "Declared crossing-location difference differs")
    ar, br = left["result"]["measured_values"], right["result"]["measured_values"]
    require(ar["authored_exception_location"] is False and
            br["authored_exception_location"] is True and
            abs((br["crossing_x_m"] - ar["crossing_x_m"]) - 45.0) <= .05,
            "Measured diagnostic comparison difference differs")
    return {"format": "c111662-unselected-saved-pair-audit-v1", "branch": branch,
            "candidate_id": candidate,
            "case_ids": [left["result"]["case_id"], right["result"]["case_id"]],
            "receipt_sha256": [left["receipt_sha256"], right["receipt_sha256"]],
            "fixed_conditions_checked": list(FIXED) + ["road.xodr", "frontage-plan.json"],
            "observed_crossing_delta_m": br["crossing_x_m"] - ar["crossing_x_m"],
            "scope": "unselected synthetic saved diagnostic; no physical or legal acceptance",
            "passed": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--contrast", required=True)
    parser.add_argument("--branch", choices=CASES, required=True)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.reference, args.contrast, args.branch, args.candidate), sort_keys=True))
