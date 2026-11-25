"""Independent saved-source gate for the selected C179819 speed cases."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_NAMES = ("road.xodr", "sign-survey.json", "street-status.json",
                "actor-poses.jsonl", "video_frames.jsonl", "reference_corner.mkv")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing source: " + path.name)
    return json.loads(path.read_text())


def audit(case, candidate, attempt, processing, diagnostic, omit_source=None):
    manifest = read(HERE / "execution-manifest.json")
    entry = next((e for e in manifest["cases"] if e["case_id"] == case), None)
    if entry is None:
        raise ValueError("Unknown selected case")
    selected = entry if candidate == "primary" else next(
        (e for e in entry["candidates"] if e["id"] == candidate), None)
    if selected is None:
        raise ValueError("Unknown selected candidate")
    saved = read(processing)
    if (saved.get("passed") is not True or saved.get("recorded_only") is not True or
            saved.get("case_id") != case or saved.get("candidate_id") != candidate or
            saved.get("native_revision", {}).get("construction_sha256") != selected["construction_sha256"] or
            saved.get("originals_preserved") is not True or
            saved.get("timestamp_joins", {}).get("frames") != 600 or
            saved.get("final_video_checks", {}).get("frames") != 600):
        raise ValueError("Selected saved processing or full-frame decode differs")
    stage = Path(saved["analysis_directory"]).resolve()
    hashes = {}
    for name in SOURCE_NAMES:
        if name == omit_source:
            raise ValueError("Missing source: " + name)
        path = stage / name
        if not path.is_file():
            raise ValueError("Missing source: " + name)
        hashes[name] = sha(path)
    result = read(stage / "result.json")
    analysis = read(stage / "analysis-report.json")
    if (result.get("case_id") != case or result.get("trace_reference") != "trace.jsonl" or
            len((stage / "trace.jsonl").read_text().splitlines()) != 600 or
            len((stage / "video_frames.jsonl").read_text().splitlines()) != 600):
        raise ValueError("Original trace or frame map differs")
    measurements = analysis.get("measurements", {})
    speed = measurements.get("source_bound_speed_and_governance", {})
    if (speed.get("method") != "speed_and_governance_measurement" or
            any(speed.get("sources", {}).get(name) != hashes[name]
                for name in ("road.xodr", "sign-survey.json", "street-status.json", "actor-poses.jsonl", "reference_corner.mkv"))):
        raise ValueError("Source-bound speed or governance measurement differs")
    value = speed.get("value", {})
    posted = case.endswith("posted_35")
    if (value.get("frame_count") != 600 or
            (value.get("posted_governed_frames", 0) > 0) != posted or
            value.get("legal_compliance") != "unassessed"):
        raise ValueError("Speed and posted-branch measurement differs")
    survey = read(stage / "sign-survey.json")
    street = read(stage / "street-status.json")
    if (survey.get("road_sha256") != hashes["road.xodr"] or
            street.get("road_sha256") != hashes["road.xodr"] or
            survey.get("pixel_source") != "reference_corner.mkv" or
            (survey.get("applicable_posted_signs") != []) == posted):
        raise ValueError("Original sign or street source join differs")
    if diagnostic:
        fixture = read(Path(attempt) / "compatibility.json")
        if (fixture.get("passed") is not True or fixture.get("case_id") != case or
                fixture.get("candidate_id") != candidate or
                fixture.get("construction_sha256") != selected["construction_sha256"]):
            raise ValueError("Diagnostic compatibility identity differs")
    else:
        provenance = read(Path(attempt) / "acquisition-provenance.json")
        if (provenance.get("provenance_kind") != "native" or provenance.get("diagnostic_fixture") is True):
            raise ValueError("Original Native acquisition required")
        for source, label in ((survey, "sign"), (street, "street")):
            if (source.get("review_status") != "independently_reviewed" or
                    not source.get("reviewer") or source.get("synthetic_diagnostic") is True):
                raise ValueError("Independent " + label + " review incomplete")
        pixels = read(stage / "sign-pixel-review.json")
        if (pixels.get("review_status") != "independently_reviewed" or
                not pixels.get("reviewer") or
                pixels.get("frame_map_sha256") != hashes["video_frames.jsonl"] or
                pixels.get("source_video_sha256") != hashes["reference_corner.mkv"] or
                pixels.get("actual_face_limit_mph") != (35 if posted else 25)):
            raise ValueError("Independent original sign pixel review incomplete")
        physical = result.get("physical_checks", {}).get("maneuver", {})
        if (physical.get("status") != "met" or result.get("maneuver_completed") is not True):
            raise ValueError("Original physical travel completion unverified")
    return {"format": "c179819-independent-delivery-audit-v1", "case_id": case,
            "candidate_id": candidate, "construction_sha256": selected["construction_sha256"],
            "saved_processing_sha256": sha(processing), "original_source_sha256": hashes,
            "diagnostic_only": diagnostic, "physical_or_legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", default="primary")
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--processing", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--omit-source", choices=SOURCE_NAMES)
    args = parser.parse_args()
    if args.omit_source and not args.diagnostic:
        raise ValueError("Source omission is diagnostic only")
    receipt = audit(args.case, args.candidate, args.attempt, args.processing,
                    args.diagnostic, args.omit_source)
    if args.output.exists():
        raise ValueError("Retain previous delivery audit result")
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"passed": True, "case_id": args.case,
                      "diagnostic_only": args.diagnostic}))


if __name__ == "__main__":
    main()
