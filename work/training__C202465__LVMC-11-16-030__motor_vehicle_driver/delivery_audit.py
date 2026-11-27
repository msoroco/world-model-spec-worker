"""Independent source-bound rail-crossing delivery audit for an exact saved case."""

import argparse
import hashlib
import json
from pathlib import Path

WORK = Path(__file__).resolve().parent
ORIGINALS = (
    "road.xodr", "rail-body.jsonl", "rail-rays.jsonl",
    "reviewed-exceptions.jsonl", "reviewed-exceptions-review.json",
    "video_frames.jsonl", "trace.jsonl",
    *("original-source-review/" + role + extension
      for role in ("railway", "approach", "flagman", "signal")
      for extension in (".json", ".source.txt")),
)
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing source: " + path.name)
    return json.loads(path.read_text())


def audit(case, candidate, attempt, processing, diagnostic, omit_source=None):
    manifest = read(WORK / "execution-manifest.json")
    entry = next((item for item in manifest["cases"] if item["case_id"] == case), None)
    if entry is None:
        raise ValueError("Unknown selected case")
    selected = entry if candidate == "primary" else next(
        (item for item in entry["candidates"] if item["id"] == candidate), None)
    if selected is None:
        raise ValueError("Unknown selected candidate")
    saved = read(processing)
    checks = saved.get("final_video_checks") or {}
    if (saved.get("passed") is not True or saved.get("recorded_only") is not True
            or saved.get("case_id") != case or saved.get("candidate_id") != candidate
            or saved.get("native_revision", {}).get("construction_sha256") != selected["construction_sha256"]
            or saved.get("originals_preserved") is not True
            or saved.get("timestamp_joins", {}).get("frames") != 600
            or saved.get("timestamp_joins", {}).get("passed") is not True
            or checks.get("frames") != 600 or not checks.get("rgb_sequence_sha256")):
        raise ValueError("Selected saved-only processing or full-frame pixels differ")
    stage = Path(saved["analysis_directory"]).resolve()
    source_hashes = {}
    for name in (*ORIGINALS, *(camera + ".mkv" for camera in CAMERAS)):
        if name == omit_source:
            raise ValueError("Missing source: " + name)
        source = stage / name
        if not source.is_file():
            raise ValueError("Missing source: " + name)
        source_hashes[name] = sha(source)
    result = read(stage / "result.json")
    report = read(stage / "analysis-report.json")
    if (result.get("case_id") != case or report.get("case_id") != case
            or result.get("trace_reference") != "trace.jsonl"
            or any(len((stage / name).read_text().splitlines()) != 600 for name in
                   ("rail-body.jsonl", "rail-rays.jsonl", "reviewed-exceptions.jsonl",
                    "trace.jsonl", "video_frames.jsonl"))):
        raise ValueError("Original 600-frame body, ray, exception or camera join differs")
    for name, measurement in report.get("measurements", {}).items():
        if (measurement.get("method") not in
                ("measure_rail_geometry", "measure_exception", "measure_selected_witness")
                or any(measurement.get("sources", {}).get(source) != digest
                       for source, digest in source_hashes.items() if source in ORIGINALS)):
            raise ValueError("Source-bound rail measurement differs: " + name)
    if not {"rail_sight_and_speed", "crossing_exceptions", "selected_witness"} <= set(report.get("measurements", {})):
        raise ValueError("Rail, exception or selected witness measurement omitted")
    for role in ("railway", "approach", "flagman", "signal"):
        review = read(stage / "original-source-review" / (role + ".json"))
        if (review.get("road_sha256") != source_hashes["road.xodr"]
                or review.get("source_sha256") != source_hashes["original-source-review/" + role + ".source.txt"]):
            raise ValueError("Original railway or exception review source join differs")
        if not diagnostic and review.get("review_status") != "independently_reviewed":
            raise ValueError("Original railway or exception review incomplete")
    if diagnostic:
        receipt = read(Path(attempt) / "compatibility.json") if (Path(attempt) / "compatibility.json").is_file() else None
        provenance = read(stage / "acquisition-provenance.json")
        if provenance.get("provenance_kind") != "synthetic_fixture":
            raise ValueError("Diagnostic fixture provenance differs")
        if receipt is not None and (receipt.get("passed") is not True or receipt.get("case_id") != case):
            raise ValueError("Diagnostic compatibility identity differs")
    else:
        provenance = read(stage / "acquisition-provenance.json")
        if provenance.get("provenance_kind") != "native" or provenance.get("diagnostic_fixture") is True:
            raise ValueError("Original Native acquisition required")
        physical = result.get("physical_checks", {}).get("maneuver", {})
        if physical.get("status") != "met" or result.get("maneuver_completed") is not True:
            raise ValueError("Original physical crossing completion unverified")
    return {"format": "lvmc-independent-delivery-audit-v1", "case_id": case,
            "candidate_id": candidate, "construction_sha256": selected["construction_sha256"],
            "saved_processing_sha256": sha(processing), "original_source_sha256": source_hashes,
            "diagnostic_only": diagnostic, "physical_or_legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", default="primary")
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--processing", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--omit-source", choices=ORIGINALS)
    args = parser.parse_args()
    if args.omit_source and not args.diagnostic:
        raise ValueError("Source omission is diagnostic only")
    value = audit(args.case, args.candidate, args.attempt, args.processing,
                  args.diagnostic, args.omit_source)
    if args.output.exists():
        raise ValueError("Retain previous delivery audit result")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps({"passed": True, "case_id": args.case, "diagnostic_only": args.diagnostic}))


if __name__ == "__main__":
    main()
