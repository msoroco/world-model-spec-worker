"""Independent selected saved-source and physical delivery audit for C109128."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = ("pedestrian-original.jsonl", "sidewalk_context.json",
           "video_frames.jsonl", "camera-sources.jsonl", "trace.jsonl",
           "overview.mkv", "approach.mkv", "reference_corner.mkv",
           "driver_reference.mkv")
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing source: " + path.name)
    return json.loads(path.read_text())


def audit(case, candidate, attempt, processing, diagnostic=False, omit_source=None):
    manifest = read(HERE / "execution-manifest.json")
    entry = next((row for row in manifest["cases"] if row["case_id"] == case), None)
    if entry is None:
        raise ValueError("Unknown exact sidewalk bypass case")
    selected = (entry if candidate == "primary" else
                next((row for row in entry["candidates"] if row["id"] == candidate), None))
    if selected is None:
        raise ValueError("Unknown exact sidewalk bypass candidate")
    saved = read(processing)
    if (saved.get("passed") is not True or saved.get("recorded_only") is not True or
            saved.get("case_id") != case or saved.get("candidate_id") != candidate or
            saved.get("native_revision", {}).get("construction_sha256") != selected["construction_sha256"] or
            saved.get("originals_preserved") is not True or saved.get("missing_evidence") is not False or
            saved.get("timestamp_joins", {}).get("frames") != 600 or
            saved.get("timestamp_joins", {}).get("passed") is not True or
            saved.get("final_video_checks", {}).get("frames") != 600):
        raise ValueError("Selected recorded-only processing or full decode differs")
    stage = Path(saved["analysis_directory"]).resolve()
    hashes = {}
    for name in SOURCES:
        if name == omit_source:
            raise ValueError("Missing source: " + name)
        path = stage / name
        if not path.is_file():
            raise ValueError("Missing source: " + name)
        hashes[name] = sha(path)
    result = read(stage / "result.json")
    analysis = read(stage / "analysis-report.json")
    context = read(stage / "sidewalk_context.json")
    if (result.get("case_id") != case or analysis.get("case_id") != case or
            context.get("source_kind") != "original_native_map_readback" or
            result.get("trace_reference") != "trace.jsonl" or
            len((stage / "trace.jsonl").read_text().splitlines()) != 600 or
            len((stage / "video_frames.jsonl").read_text().splitlines()) != 600 or
            len((stage / "pedestrian-original.jsonl").read_text().splitlines()) != 600 or
            len((stage / "camera-sources.jsonl").read_text().splitlines()) != 2400):
        raise ValueError("Original pedestrian, map or four-view time join differs")
    contract = read(HERE / entry["measurement_contract"])
    measurements = analysis.get("measurements", {})
    for row in contract["requirements"]:
        item = measurements.get(row["output_key"], {})
        if (item.get("method") != row["method"] or not item.get("value") or
                any(item.get("sources", {}).get(name) != hashes[name]
                    for name in row["inputs"])):
            raise ValueError("Selected original measurement source differs")
    if result.get("measured_values", {}).get("first_full_sidewalk_return_frame") is None:
        raise ValueError("No source-measured full sidewalk return")
    if diagnostic:
        compatibility = read(Path(attempt) / "compatibility.json")
        if (compatibility.get("passed") is not True or compatibility.get("case_id") != case or
                compatibility.get("candidate_id") != candidate or
                compatibility.get("construction_sha256") != selected["construction_sha256"] or
                result.get("provenance_kind") != "synthetic_fixture" or
                result.get("diagnostic_fixture") is not True):
            raise ValueError("Synthetic diagnostic source identity differs")
    else:
        provenance = read(Path(attempt) / "acquisition-provenance.json")
        if (provenance.get("provenance_kind") != "native" or
                provenance.get("diagnostic_fixture") is True or
                result.get("provenance_kind") != "original_native" or
                result.get("diagnostic_fixture") is True):
            raise ValueError("Original Native source provenance absent")
        pixels = read(stage / "pixel-review.json")
        if (pixels.get("review_status") != "independently_reviewed" or
                not pixels.get("reviewer") or
                pixels.get("frame_map_sha256") != hashes["video_frames.jsonl"] or
                pixels.get("camera_sha256") != {name: hashes[name + ".mkv"] for name in CAMERAS} or
                pixels.get("pedestrian_visible") is not True or
                pixels.get("obstruction_visible") is not True or
                pixels.get("sidewalk_and_adjacent_highway_visible") is not True):
            raise ValueError("Original physical pixels lack independent review")
        physical = read(stage / "physical-review.json")
        if (physical.get("review_status") != "independently_reviewed" or
                not physical.get("reviewer") or
                physical.get("source_sha256") != {name: hashes[name] for name in
                                                   ("pedestrian-original.jsonl", "sidewalk_context.json",
                                                    "video_frames.jsonl")} or
                physical.get("geometric_bypass_and_return") is not True or
                physical.get("actual_obstruction_confirmed") is not True or
                physical.get("first_practicable_return_reviewed") is not True or
                physical.get("due_care_reviewed") is not True):
            raise ValueError("Physical completion lacks independent original-source review")
    return {"format": "worker-sidewalk-bypass-delivery-audit",
            "case_id": case, "candidate_id": candidate,
            "construction_sha256": selected["construction_sha256"],
            "saved_processing_sha256": sha(processing),
            "source_sha256": hashes, "diagnostic_only": diagnostic,
            "physical_or_legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", default="primary")
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--processing", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--omit-source", choices=SOURCES)
    args = parser.parse_args()
    if args.omit_source and not args.diagnostic:
        raise ValueError("Diagnostic source omission only")
    receipt = audit(args.case, args.candidate, args.attempt, args.processing,
                    args.diagnostic, args.omit_source)
    if args.output.exists():
        raise ValueError("Retain previous delivery audit result")
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"case_id": args.case, "diagnostic_only": args.diagnostic,
                      "source_count": len(receipt["source_sha256"])}, sort_keys=True))
