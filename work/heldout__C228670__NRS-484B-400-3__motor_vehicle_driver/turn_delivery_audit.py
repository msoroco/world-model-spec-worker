"""Independently check saved turn measurements against unchanged original sources."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
from worker_exchange.media import audit as audit_video
from turn_position_finalizer import CHANNELS, SOURCES, analyze_attempt

CAMERAS = ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit(case, attempt, processed, manifest_name="provisional-manifest.json", negative_source=False):
    manifest = json.loads((HERE / manifest_name).read_text())
    entry = next((item for item in manifest["cases"] if item["case_id"] == case), None)
    require(entry is not None and entry["kind"] == "delivery", "Unknown exact turn delivery case")
    attempt, processed = Path(attempt), Path(processed)
    receipt = json.loads((HERE / entry["saved_processing"]["receipt"]).read_text())
    report = json.loads((processed / "v0001/analysis/analysis-report.json").read_text())
    require(receipt["case_id"] == report["case_id"] == case and receipt["passed"]
            and receipt["originals_preserved"] and not receipt["missing_evidence"],
            "Wrong saved turn case, missing evidence or changed originals")
    require(receipt["native_revision"]["construction_sha256"] == entry["construction_sha256"],
            "Stale exact turn construction")
    sources = {name: digest(attempt / name) for name in SOURCES}
    if negative_source:
        sources["route_survey_original.json"] = "0" * 64
    for name, value in sources.items():
        require(receipt["original_source_hashes"].get(name) == value,
                "Stale or missing original turn source: " + name)
    measured = analyze_attempt(attempt, write_channels=False)
    require(report["measurements"] == measured["measurements"] and report["case_id"] == measured["case_id"],
            "Saved turn measurement changed from original sources")
    body = rows(attempt / "body_corners_original.jsonl")
    mapping = rows(attempt / "video_frames.jsonl")
    trace = rows(attempt / "trace.jsonl")
    require(len(body) == len(mapping) == len(trace) > 0,
            "Incomplete original turn frame inventory")
    for index, (sample, frame, motion) in enumerate(zip(body, mapping, trace)):
        identity = sample["frame"], sample["time_s"]
        require((frame["carla_frame"], frame["time_s"]) == identity
                and (motion["frame"], motion["time_s"]) == identity
                and frame["video_frame"] == index, "Original turn frame join differs")
        center = [sum(corner[axis] for corner in sample["body_corners_xy_m"]) / 4 for axis in (0, 1)]
        require(all(abs(center[axis] - motion["position_m"][axis]) < .05 for axis in (0, 1)),
                "Original turn body/trace pose differs")
    for name in CAMERAS:
        audit_video(attempt / name, len(mapping), mapping_sha256=sources["video_frames.jsonl"])
    require(report.get("physical_acceptance_claimed") is False
            and report.get("legal_acceptance_claimed") is False
            and set(CHANNELS) <= set(report["measurements"]),
            "Saved turn report omits measurements or makes unsupported finding")
    return {"format": "worker-turn-delivery-source-audit", "case_id": case,
            "joined_frames": len(mapping), "decoded_cameras": list(CAMERAS),
            "route_source_sha256": sources["route_survey_original.json"],
            "original_source_integrity_passed": True,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--processed", required=True)
    parser.add_argument("--manifest-name", default="provisional-manifest.json")
    parser.add_argument("--negative-source", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.processed, args.manifest_name,
                          args.negative_source), indent=2))
