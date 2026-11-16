"""Independent source audit of a saved turn-indication diagnostic attempt."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))

from worker_exchange.media import audit as audit_video
from turn_marking import analyze_original_sources

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(case, attempt, processed, manifest):
    attempt, processed, manifest = map(Path, (attempt, processed, manifest))
    entries = [item for item in read(manifest)["cases"] if item["case_id"] == case]
    require(len(entries) == 1, "Unknown exact turn-indication case")
    entry = entries[0]
    spec = entry.get("saved_processing", {})
    receipt_path = HERE / spec.get("receipt", "")
    require(receipt_path.is_file() and sha(receipt_path) == spec.get("receipt_sha256"),
            "Stale or missing returned saved-processing receipt")
    receipt = read(receipt_path)
    require(receipt.get("case_id") == case and receipt.get("passed") is True
            and receipt.get("recorded_only") is True
            and receipt.get("originals_preserved") is True,
            "Saved-processing identity or original preservation differs")
    require(receipt.get("native_revision", {}).get("construction_sha256")
            == entry["construction_sha256"], "Saved construction changed")
    measured = analyze_original_sources(attempt)
    require(measured["case_id"] == case and len(measured["samples"]) >= 3,
            "Original case or turn sample coverage differs")
    hashes = measured["source_sha256"]
    require(all(receipt.get("original_source_hashes", {}).get(name) == digest
                for name, digest in hashes.items()),
            "Saved receipt differs from original turn sources")
    report_path = processed / "v0001/analysis/analysis-report.json"
    result_path = processed / "v0001/analysis/result.json"
    require(report_path.is_file() and result_path.is_file(),
            "Saved turn analysis or Native result missing")
    report, result = read(report_path), read(result_path)
    require(report.get("case_id") == result.get("case_id") == case,
            "Saved turn analysis selected another case")
    require(report.get("physical_acceptance_claimed") is False
            and report.get("legal_acceptance_claimed") is False
            and result.get("physical_acceptance_claimed") is False
            and result.get("legal_acceptance_claimed") is False,
            "Software diagnostic makes unsupported acceptance claim")
    observations = report["measurements"]
    expected = {
        "original_course_deviation_m": "deviation_m",
        "original_turn_path_length_m": "path_length_m",
        "intersection_occupancy": "inside_intersection",
    }
    for channel, field in expected.items():
        item = observations[channel]
        values = [{"frame": sample["frame"], "time_s": sample["time_s"],
                   "value": sample[field]} for sample in measured["samples"]]
        require(item["value"] == values and item["sources"] == hashes,
                "Saved turn measurement differs from originals: " + channel)
    contexts = observations["turn_course_source_context"]
    require(contexts["sources"] == hashes
            and len(contexts["value"]) == len(measured["samples"]),
            "Saved turn source context coverage differs")
    for row, sample in zip(contexts["value"], measured["samples"]):
        value = row["value"]
        require((row["frame"], row["time_s"])
                == (sample["frame"], sample["time_s"])
                and value["indication_form"] == measured["indication_form"]
                and value["intersection_id"] == measured["intersection_id"]
                and value["authorization_verified_by_worker"] is False,
                "Saved indication context differs from original source")
    require(result.get("video_references") == [name + ".mkv" for name in CAMERAS],
            "Four named source cameras missing")
    for name in CAMERAS:
        audit_video(attempt / (name + ".mkv"), len(measured["samples"]),
                    mapping_sha256=hashes["video_frames.jsonl"])
    require(receipt.get("timestamp_joins", {}).get("passed") is True
            if isinstance(receipt.get("timestamp_joins"), dict)
            else bool(receipt.get("timestamp_joins")),
            "Saved processing lacks original timestamp joins")
    return {"format": "worker-turn-indication-delivery-audit",
            "case_id": case, "joined_frames": len(measured["samples"]),
            "original_source_hashes": hashes, "decoded_cameras": list(CAMERAS),
            "source_integrity_passed": True,
            "municipal_authorization_verified": False,
            "actual_pixels_verified": False,
            "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--processed", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=HERE / "provisional-manifest.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.case, args.attempt, args.processed, args.manifest)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("turn_indication_delivery_source_audit_passed", args.case)
