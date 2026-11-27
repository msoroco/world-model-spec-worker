"""Independent saved-source audit for selected shoulder lamp diagnostics."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCES = ("shoulder_lighting_survey.json", "shoulder-lamp-trace.jsonl",
           "optical_measurements.json", "trace.jsonl", "video_frames.jsonl",
           "capture/evidence.jsonl", "overview.mkv", "approach.mkv",
           "reference_corner.mkv", "driver_reference.mkv")


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing source: " + path.name)
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_near_side(stage, survey, review):
    source = survey.get("near_side_installation_source")
    if not isinstance(source, dict) or source.get("path") != "lamp-installation-survey.json":
        raise ValueError("Original near-side lamp installation source missing")
    path = stage / source["path"]
    if not path.is_file() or source.get("sha256") != sha(path) or \
            review.get("near_side_installation_source_sha256") != sha(path):
        raise ValueError("Original near-side lamp installation source hash differs")
    installation = read(path)
    if (installation.get("source_kind") != "original_lamp_installation_survey" or
            installation.get("passing_traffic_side") != survey.get("passing_traffic_side") or
            installation.get("near_side_lamp_side") != survey.get("passing_traffic_side") or
            not installation.get("lamp_mount_observation") or
            not installation.get("near_as_practicable_method") or
            review.get("passing_traffic_side") != survey.get("passing_traffic_side") or
            review.get("near_side_installation_verified") is not True or
            not review.get("near_side_installation_method")):
        raise ValueError("Original near-side lamp placement differs or lacks review")


def audit(case, candidate, attempt, processing, diagnostic, omit_source):
    manifest = read(ROOT / "selected-proof-manifest.json")
    entry = next((item for item in manifest["cases"] if item["case_id"] == case), None)
    if entry is None or candidate != "primary":
        raise ValueError("Unknown selected case or candidate")
    attempt, processing = Path(attempt), Path(processing)
    saved = read(processing)
    if (saved.get("passed") is not True or saved.get("recorded_only") is not True or
            saved.get("case_id") != case or saved.get("candidate_id") != candidate or
            saved.get("originals_preserved") is not True or
            saved.get("missing_evidence") is not False or
            saved.get("timestamp_joins", {}).get("frames") != 600 or
            saved.get("final_video_checks", {}).get("frames") != 600 or
            read(attempt / "construction.json") != read(ROOT / entry["construction"])):
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
    frames = [json.loads(line) for line in (stage / "video_frames.jsonl").read_text().splitlines()]
    lamps = [json.loads(line) for line in (stage / "shoulder-lamp-trace.jsonl").read_text().splitlines()]
    if (len(trace) != 600 or len(frames) != 600 or len(lamps) != 600 or
            any(row["frame"] != frame["carla_frame"] or lamp["native_frame"] != row["frame"]
                for row, frame, lamp in zip(trace, frames, lamps))):
        raise ValueError("Original lamp or frame/time join differs")
    survey = read(stage / "shoulder_lighting_survey.json")
    if not survey.get("adjacent_paved_shoulder_source") or not survey.get("lighting_hours_source"):
        raise ValueError("Original shoulder or lighting source missing")
    result, report = read(stage / "result.json"), read(stage / "analysis-report.json")
    measurement = next(iter(report.get("measurements", {}).values()), {})
    if (result.get("case_id") != case or result.get("legal_verdict_claimed") is not False or
            result.get("trace_reference") != "trace.jsonl" or
            any(measurement.get("sources", {}).get(name) != hashes[name]
                for name in ("shoulder-lamp-trace.jsonl", "video_frames.jsonl",
                             "shoulder_lighting_survey.json", "optical_measurements.json"))):
        raise ValueError("Source-bound shoulder lamp diagnostic differs")
    if diagnostic:
        receipt = read(attempt / "compatibility.json")
        if receipt.get("passed") is not True or receipt.get("case_id") != case or \
                receipt.get("candidate_id") != candidate:
            raise ValueError("Diagnostic compatibility identity differs")
    else:
        provenance = read(attempt / "acquisition-provenance.json")
        if provenance.get("provenance_kind") != "native" or \
                provenance.get("diagnostic_fixture") is True:
            raise ValueError("Original Native source required")
        review = read(stage / "pixel-review.json")
        if (review.get("review_status") != "independently_reviewed" or
                not review.get("reviewer") or
                review.get("frame_map_sha256") != hashes["video_frames.jsonl"] or
                review.get("source_video_sha256") != hashes["reference_corner.mkv"] or
                review.get("optical_measurement_sha256") != hashes["optical_measurements.json"] or
                review.get("near_side_installation_verified") is not True):
            raise ValueError("Independent original optical, pixel or near-side lamp review incomplete")
        verify_near_side(stage, survey, review)
        if result.get("physical_checks", {}).get("maneuver", {}).get("status") != "met":
            raise ValueError("Original physical completion unverified")
    return {"format": "c183085-independent-delivery-audit-v1", "case_id": case,
            "candidate_id": candidate, "saved_processing_sha256": sha(processing),
            "source_sha256": hashes, "diagnostic_only": diagnostic,
            "physical_or_legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    for name in ("case", "attempt", "processing", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--candidate", default="primary")
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--omit-source", choices=SOURCES)
    args = parser.parse_args()
    result = audit(args.case, args.candidate, args.attempt, args.processing,
                   args.diagnostic, args.omit_source)
    output = Path(args.output)
    if output.exists():
        raise ValueError("Retain previous delivery audit result")
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "case_id": args.case,
                      "diagnostic_only": args.diagnostic}))


if __name__ == "__main__":
    main()
