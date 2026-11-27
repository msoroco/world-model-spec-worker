"""Independent saved-source audit for the exact pedestrian due-care cases."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCES = ("road_survey.json", "pedestrian-due-care-trace.jsonl", "contact_events.jsonl",
           "trace.jsonl", "video_frames.jsonl", "capture/evidence.jsonl",
           "overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing source: " + path.name)
    return json.loads(path.read_text())


def audit(case, candidate, attempt, processing, diagnostic, omit_source):
    manifest = read(ROOT / "execution-manifest.json")
    entry = next((item for item in manifest["cases"] if item["case_id"] == case), None)
    if entry is None:
        raise ValueError("Unknown selected case")
    selected = entry if candidate == "primary" else next(
        (item for item in entry["candidates"] if item["id"] == candidate), None)
    if selected is None:
        raise ValueError("Unknown candidate")
    attempt, processing = Path(attempt), Path(processing)
    saved = read(processing)
    if (saved.get("passed") is not True or saved.get("recorded_only") is not True or
            saved.get("case_id") != case or saved.get("candidate_id") != candidate or
            saved.get("originals_preserved") is not True or saved.get("missing_evidence") is not False or
            saved.get("timestamp_joins", {}).get("frames") != 600 or
            saved.get("final_video_checks", {}).get("frames") != 600 or
            read(attempt / "construction.json") != read(ROOT / selected["construction"])):
        raise ValueError("Selected saved processing or final decode differs")
    stage = Path(saved["analysis_directory"])
    hashes = {}
    for name in SOURCES:
        if name == omit_source:
            raise ValueError("Missing source: " + name)
        path = stage / name
        if not path.is_file():
            raise ValueError("Missing source: " + name)
        hashes[name] = sha(path)
    trace = [json.loads(line) for line in (stage / "trace.jsonl").read_text().splitlines()]
    mapping = [json.loads(line) for line in (stage / "video_frames.jsonl").read_text().splitlines()]
    pedestrian = [json.loads(line) for line in (stage / "pedestrian-due-care-trace.jsonl").read_text().splitlines()]
    if (len(trace) != 600 or len(mapping) != 600 or len(pedestrian) != 600 or
            any(row["frame"] != frame["carla_frame"] for row, frame in zip(trace, mapping))):
        raise ValueError("Original participant or frame/time join differs")
    survey = read(stage / "road_survey.json")
    if survey.get("pedestrian_crosses_vehicle_path") is not True:
        raise ValueError("Original pedestrian path survey missing")
    result = read(stage / "result.json")
    report = read(stage / "analysis-report.json")
    if (result.get("case_id") != case or result.get("legal_verdict_claimed") is not False or
            result.get("trace_reference") != "trace.jsonl" or
            report.get("measurements", {}).get("pedestrian_encounter_gap", {}).get("sources", {}).get(
                "pedestrian-due-care-trace.jsonl") != hashes["pedestrian-due-care-trace.jsonl"]):
        raise ValueError("Source-bound due-care diagnostic differs")
    if diagnostic:
        receipt = read(attempt / "compatibility.json")
        if (receipt.get("passed") is not True or receipt.get("case_id") != case or
                receipt.get("candidate_id") != candidate):
            raise ValueError("Diagnostic compatibility identity differs")
    else:
        provenance = read(attempt / "acquisition-provenance.json")
        if provenance.get("provenance_kind") != "native" or provenance.get("diagnostic_fixture") is True:
            raise ValueError("Original Native source required")
        review = read(stage / "pixel-review.json")
        if (review.get("review_status") != "independently_reviewed" or not review.get("reviewer") or
                review.get("frame_map_sha256") != hashes["video_frames.jsonl"] or
                review.get("source_video_sha256") != hashes["reference_corner.mkv"]):
            raise ValueError("Independent original pixel review incomplete")
        if result.get("physical_checks", {}).get("maneuver", {}).get("status") != "met":
            raise ValueError("Original physical completion unverified")
    return {"format": "c230266-independent-delivery-audit-v1", "case_id": case,
            "candidate_id": candidate, "saved_processing_sha256": sha(processing),
            "source_sha256": hashes, "checks": ["native_source", "all_participants", "time_join",
                                                  "full_video_decode", "actual_pixels", "physical_completion"],
            "diagnostic_only": diagnostic, "physical_or_legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", default="primary")
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--processing", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--omit-source", choices=SOURCES)
    args = parser.parse_args()
    result = audit(args.case, args.candidate, args.attempt, args.processing,
                   args.diagnostic, args.omit_source)
    output = Path(args.output)
    if output.exists():
        raise ValueError("Retain previous delivery audit result")
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "case_id": args.case, "diagnostic_only": args.diagnostic}))


if __name__ == "__main__":
    main()
