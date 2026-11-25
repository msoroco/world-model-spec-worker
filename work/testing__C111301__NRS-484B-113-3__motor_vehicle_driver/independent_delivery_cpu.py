"""Independently exercise source, pixels and motion on diagnostic attempts.

These tests specify the acceptance checks; a synthetic pass never certifies an
original CARLA capture or the legal judgment.
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "runtime"))
sys.path.insert(0, str(HERE))
from media_decode import audit_media
from saved_backing import _sealed as sealed
from scenario_pipeline.worker_exchange.native_output import physical_result


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(attempt, case, scratch, negative=False):
    attempt = Path(attempt).resolve()
    if case not in {HERE.name + "__" + suffix for suffix in (
            "pedestrian_yield", "pedestrian_continue", "traffic_yield", "traffic_continue")}:
        raise ValueError("another exact case selected")
    receipt = json.loads((attempt / "acquisition.json").read_text())
    if receipt.get("case_id") != case or receipt.get("source_kind") != "synthetic_fixture" or receipt.get("diagnostic") is not True:
        raise ValueError("diagnostic source identity differs")
    if negative:
        scratch = Path(scratch)
        scratch.mkdir(parents=True, exist_ok=True)
        (scratch / "approach.mkv").write_bytes((attempt / "approach.mkv").read_bytes() + b"tamper")
        try:
            sealed(scratch, receipt["media"]["approach"])
        except ValueError as error:
            raise ValueError("original source changed: approach.mkv") from error
        raise ValueError("tampered original video accepted")
    source = __import__("traffic_saved" if "__traffic_" in case else "saved_backing")
    measured = source.process(attempt, case, allow_diagnostic=True)
    original_hashes = {name: digest(attempt / name) for name in (
        "acquisition.json", "config.json", "trace.jsonl", "video_frames.jsonl",
        "map.json", "road.xodr", "telemetry.json", "frame-map.json")}
    pixels = audit_media(attempt, receipt)
    motion = physical_result(attempt, {"target_checks": []})
    if motion["physical_checks"]["maneuver"]["status"] != "met":
        raise ValueError("diagnostic motion fixture lacks finite reverse displacement")
    if any(digest(attempt / name) != value for name, value in original_hashes.items()):
        raise ValueError("original source changed during independent audit")
    return {"format": "c111301-independent-diagnostic-audit", "case_id": case,
            "source_hashes": original_hashes, "measurement_source_sha256": measured["acquisition_sha256"],
            "pixels": pixels, "motion_check": motion["physical_checks"]["maneuver"],
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "original_physical_acceptance": False, "legal_judgment": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--scratch", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    report = check(args.attempt, args.case, args.scratch, args.negative)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print("independent diagnostic source, pixel and motion audit passed")
