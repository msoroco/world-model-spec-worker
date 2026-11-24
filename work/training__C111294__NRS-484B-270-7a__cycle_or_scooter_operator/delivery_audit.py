"""Exact bicycle/motorist source audit; CPU diagnostic never accepts a legal result."""

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing source: " + path.name)
    return json.loads(path.read_text())


def audit(case, candidate, attempt, processing, diagnostic):
    manifest = read(HERE / "execution-manifest.json")
    matches = [x for x in manifest["cases"] if x["case_id"] == case]
    if len(matches) != 1:
        raise ValueError("Exact selected case required")
    entry = matches[0]
    selected = entry if candidate == "primary" else next(
        (x for x in entry["candidates"] if x["id"] == candidate), None)
    if selected is None:
        raise ValueError("Exact candidate required")
    attempt = Path(attempt)
    compatibility = read(attempt / "compatibility.json") if diagnostic else None
    saved = read(processing)
    result = read(attempt / "result.json")
    analysis = read(attempt / "analysis-report.json")
    measurement = analysis["measurements"]["bicycle_motorist_interaction"]["value"]
    if any((saved.get("passed") is not True,
            saved.get("recorded_only") is not True,
            saved.get("case_id") != case,
            saved.get("candidate_id") != candidate,
            saved.get("timestamp_joins", {}).get("frames") != 600,
            saved.get("final_video_checks", {}).get("frames") != 600,
            result.get("accepted") is not False,
            result.get("legal_verdict_claimed") is not False,
            measurement.get("frames") != 600,
            measurement.get("legal_interference_claimed") is not False,
            measurement.get("intent_physically_verified") is not False)):
        raise ValueError("Saved source or nonverdict measurement differs")
    if diagnostic:
        if any((compatibility.get("passed") is not True,
                compatibility.get("case_id") != case,
                compatibility.get("candidate_id") != candidate,
                compatibility.get("construction_sha256") != selected["construction_sha256"],
                compatibility.get("negative_removed") != "interaction.json",
                compatibility.get("negative_log_sha256") != sha(attempt / "negative-analysis.log"),
                measurement.get("physical_behavior_observed") is not False)):
            raise ValueError("Diagnostic compatibility source differs")
    else:
        if (result.get("provenance_kind") != "native" or
                measurement.get("physical_behavior_observed") is not True):
            raise ValueError("Original Native source required")
        review = read(attempt / "independent-original-review.json")
        if (review.get("source_kind") != "independent_original_capture_review" or
                review.get("case_id") != case or
                review.get("qualifying_bicycle_operator") is not True or
                review.get("separate_motor_vehicle") is not True or
                review.get("full_body_visible") is not True or
                review.get("movement_effect_reviewed") is not True or
                review.get("intent_review_status") != "reviewed_independently" or
                not review.get("original_source_refs")):
            raise ValueError("Original bicycle, motorist, pixel and intent review incomplete")
    return {"format": "c111294-source-bound-delivery-audit-v1",
            "case_id": case, "candidate_id": candidate,
            "construction_sha256": selected["construction_sha256"],
            "compatibility_sha256": sha(attempt / "compatibility.json") if diagnostic else None,
            "processing_sha256": sha(processing),
            "analysis_sha256": sha(attempt / "analysis-report.json"),
            "diagnostic_only": diagnostic,
            "physical_or_legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", default="primary")
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--processing", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    result = audit(args.case, args.candidate, args.attempt, args.processing,
                   args.diagnostic)
    if args.output.exists():
        raise ValueError("Audit output already exists")
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "case_id": args.case,
                      "diagnostic_only": args.diagnostic}))


if __name__ == "__main__":
    main()
