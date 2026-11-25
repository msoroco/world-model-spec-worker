"""Independent original-source and recorded-only delivery audit."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "native"))
from finalize import analyze

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
ROLES = ("required-stop", "rail-crossing", "right-edge",
         "lane-markings", "right-availability", "gate-indication")


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
        raise ValueError("Recorded-only saved processing binding incomplete")
    provenance = read(attempt / "acquisition-provenance.json")
    if diagnostic:
        if provenance.get("provenance_kind") != "synthetic_fixture":
            raise ValueError("Diagnostic provenance missing")
    elif not (attempt / "capture-seal.json").is_file():
        raise ValueError("Original sealed Native capture missing")
    originals = receipt.get("original_source_hashes", {})
    required = ("actors.jsonl", "gate.jsonl", "geometry.json",
                "video_frames.jsonl", "rail-inventory.json", "sources.json",
                "road.xodr", "trace.jsonl",
                *("rail-review/" + role + suffix for role in ROLES
                  for suffix in (".json", ".source.txt")),
                *(name + ".mkv" for name in CAMERAS))
    for name in required:
        if name not in originals or not (attempt / name).is_file() or sha(attempt / name) != originals[name]:
            raise ValueError("Original source missing or stale: " + name)
    measured = analyze(attempt)
    if measured["case_id"] != case:
        raise ValueError("Measured case identity differs")
    stage = Path(receipt["version"]).resolve()
    if stage / "processing.json" != processing:
        raise ValueError("Processing version path differs")
    mapping_sha = originals["video_frames.jsonl"]
    decodes = [read(stage / ("source-" + str(i) + ".json")) for i in range(4)]
    for camera in CAMERAS:
        if not any(item.get("format") == "source-decode" and item.get("passed") is True and
                   item.get("frames") == 600 and item.get("mapping_sha256") == mapping_sha and
                   item.get("video_sha256") == originals[camera + ".mkv"] and
                   item.get("rgb_sequence_sha256") for item in decodes):
            raise ValueError("Full source decode binding differs: " + camera)
    result = read(receipt["result"])
    if result.get("case_id") != case or result.get("legal_verdict_claimed") is not False:
        raise ValueError("Saved result identity or legal boundary differs")
    physical = None
    if not diagnostic:
        path = attempt / "original-physical-review.json"
        if not path.is_file():
            raise ValueError("Original physical and pixel review missing")
        physical = read(path)
        if not all(physical.get(key) is True for key in
                   ("native_source", "all_participants", "time_join",
                    "actual_pixels", "physical_completion")) or physical.get(
                        "capture_seal_sha256") != sha(attempt / "capture-seal.json"):
            raise ValueError("Original physical review incomplete")
    return {"format": "c202463-diagnostic-delivery-audit" if diagnostic else
            "worker-delivery-audit", "case_id": case,
            "processing_sha256": sha(processing),
            "source_hashes": {name: originals[name] for name in required},
            "checks": {"native_source": not diagnostic, "all_participants": True,
                       "time_join": True, "full_video_decode": True,
                       "actual_pixels": physical is not None,
                       "physical_completion": physical is not None},
            "marked_lanes_measured": measured["measurement"]["total_marked_lanes"],
            "abreast_frames_measured": measured["measurement"]["abreast_two_queue_frames"],
            "physical_acceptance_claimed": physical is not None,
            "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for option in ("case", "attempt", "processing", "output"):
        parser.add_argument("--" + option, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    value = audit(args.case, args.attempt, args.processing, args.diagnostic)
    Path(args.output).write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps(value, sort_keys=True))
