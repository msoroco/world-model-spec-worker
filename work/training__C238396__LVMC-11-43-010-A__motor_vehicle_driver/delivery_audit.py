"""Independent exact-case source and delivery audit for roundabout entry."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "native"))
from finalize import analyze

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def audit(case, attempt, processing, diagnostic=False):
    attempt, processing = Path(attempt).resolve(), Path(processing).resolve()
    receipt = read(processing)
    if (receipt.get("format") != "worker-saved-processing" or
            receipt.get("case_id") != case or receipt.get("passed") is not True or
            receipt.get("recorded_only") is not True or
            receipt.get("originals_preserved") is not True or
            receipt.get("timestamp_joins", {}).get("frames") != 600):
        raise ValueError("Saved processing binding incomplete")
    provenance = read(attempt / "acquisition-provenance.json")
    if diagnostic:
        if provenance.get("provenance_kind") != "synthetic_fixture":
            raise ValueError("Diagnostic mode requires an identified CPU fixture")
    elif not (attempt / "capture-seal.json").is_file():
        raise ValueError("Original sealed Native capture missing")
    originals = receipt.get("original_source_hashes", {})
    required = ("native-raw-actors.jsonl", "control-intent.jsonl",
                "video_frames.jsonl", "roundabout-map-readback.json", "road.xodr",
                "trace.jsonl", *(name + ".mkv" for name in CAMERAS))
    for name in required:
        if name not in originals or not (attempt / name).is_file() or sha(attempt / name) != originals[name]:
            raise ValueError("Original source missing or stale: " + name)
    measurement = analyze(attempt)
    if measurement["case_id"] != case:
        raise ValueError("Measured case identity differs")
    stage = Path(receipt["version"]).resolve()
    if stage / "processing.json" != processing:
        raise ValueError("Processing version path differs")
    map_sha = originals["video_frames.jsonl"]
    video_receipts = {}
    for index, camera in enumerate(CAMERAS):
        source = stage / ("source-" + str(index) + ".json")
        value = read(source)
        if (value.get("format") != "source-decode" or value.get("passed") is not True or
                value.get("frames") != 600 or value.get("mapping_sha256") != map_sha or
                value.get("video_sha256") != originals[camera + ".mkv"] or
                not value.get("rgb_sequence_sha256")):
            raise ValueError("Full source decode binding differs: " + camera)
        video_receipts[camera] = {"path": str(source), "sha256": sha(source),
                                  "rgb_sequence_sha256": value["rgb_sequence_sha256"]}
    result = read(receipt["result"])
    if result.get("case_id") != case or result.get("legal_verdict_claimed") is not False:
        raise ValueError("Saved result identity or legal boundary differs")
    physical = None
    if not diagnostic:
        review_path = attempt / "original-physical-review.json"
        if not review_path.is_file():
            raise ValueError("Original physical and pixel review missing")
        physical = read(review_path)
        if (physical.get("case_id") != case or
                physical.get("capture_seal_sha256") != sha(attempt / "capture-seal.json") or
                physical.get("native_source") is not True or
                physical.get("all_participants") is not True or
                physical.get("time_join") is not True or
                physical.get("actual_pixels") is not True or
                physical.get("physical_completion") is not True):
            raise ValueError("Original physical review incomplete or stale")
    return {"format": "c239014-delivery-audit-diagnostic-v1" if diagnostic else
            "worker-delivery-audit", "case_id": case, "diagnostic_fixture": diagnostic,
            "processing_sha256": sha(processing), "source_hashes": {name: originals[name]
                                                          for name in required},
            "checks": {"native_source": not diagnostic, "all_participants": True,
                       "time_join": True, "full_video_decode": True,
                       "actual_pixels": physical is not None,
                       "physical_completion": physical is not None},
            "source_decode_receipts": video_receipts,
            "measured_entry_frame": measurement["first_entry_frame"],
            "physical_acceptance_claimed": physical is not None,
            "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--processing", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    value = audit(args.case, args.attempt, args.processing, args.diagnostic)
    Path(args.output).write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps(value, sort_keys=True))
