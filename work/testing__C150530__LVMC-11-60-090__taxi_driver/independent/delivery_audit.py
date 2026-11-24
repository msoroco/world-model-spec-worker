"""Independent delivery audit for an original taxi-stand attempt.

The pixel review is a human-authored observation of original decoded frames.
This program verifies its source bindings and required observations; it never
infers visibility from the diagnostic colour fixture.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE_SPEC = importlib.util.spec_from_file_location("taxi_source_audit", ROOT / "delivery_audit.py")
SOURCE_AUDIT = importlib.util.module_from_spec(SOURCE_SPEC)
assert SOURCE_SPEC.loader is not None
SOURCE_SPEC.loader.exec_module(SOURCE_AUDIT)
audit_source_chain = SOURCE_AUDIT.audit_source_chain
verify_decode_receipt = SOURCE_AUDIT.verify_decode_receipt
from original_motion_consistency import check as check_motion_consistency

ASSIGNMENT = ROOT.name
CASES = ("near_stand", "far_stand", "near_stand_straight")
CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")
PIXELS = ("taxi", "stand_marking", "posted_notice", "first_intersection", "maneuver")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def verify_evidence(case_id: str, source: dict, decode: dict, physical: dict,
                    pixels: dict, core: dict, attempt: Path) -> dict:
    """Join independent observations to exact original source bytes and frames."""
    if case_id not in {ASSIGNMENT + "__" + name for name in CASES}:
        raise ValueError("unknown exact case")
    if source.get("case_id") != case_id or source.get("passed") is not True:
        raise ValueError("Native source chain unverified")
    if decode.get("case_id") != case_id or decode.get("passed") is not True:
        raise ValueError("full video decode unverified")
    physical_checks = physical.get("physical_checks", {})
    if (physical.get("case_id") != case_id or
            physical.get("provenance_kind") != "native" or
            physical.get("diagnostic_fixture") is not False or
            not physical.get("setup_confirmed") or
            not physical.get("maneuver_completed") or
            not {"setup", "target", "maneuver"} <= set(physical_checks) or
            any(item.get("status") != "met" for item in physical_checks.values())):
        raise ValueError("physical completion unverified")
    for item in physical_checks.values():
        sources = item.get("sources", {})
        if not sources:
            raise ValueError("physical completion lacks source bindings")
        for name, digest in sources.items():
            path = (attempt / name).resolve()
            if not path.is_relative_to(attempt.resolve()) or not path.is_file() or sha(path) != digest:
                raise ValueError("physical completion source changed: " + name)
    video = attempt / "raw.mkv"
    mapping = attempt / "video_frames.jsonl"
    trace = attempt / "traffic_spec" / "trace.json"
    if decode.get("video_sha256") != sha(video):
        raise ValueError("decoded video source changed")
    if source.get("frame_map_sha256") != sha(mapping):
        raise ValueError("original frame map changed")
    scenes = core.get("scenes")
    rows = [json.loads(line) for line in mapping.read_text().splitlines()]
    if not isinstance(scenes, list) or len(scenes) != len(rows) or len(rows) != source.get("frames"):
        raise ValueError("Core trace/frame count differs")
    for index, (scene, row) in enumerate(zip(scenes, rows)):
        if row.get("video_frame") != index or scene.get("t") != round(row["time_s"] * 1000):
            raise ValueError("Core trace/original frame time join differs")
    if pixels.get("format") != "worker-original-pixel-review" or pixels.get("case_id") != case_id:
        raise ValueError("original pixel review missing")
    if pixels.get("video_sha256") != sha(video) or pixels.get("frame_map_sha256") != sha(mapping) or pixels.get("core_trace_sha256") != sha(trace):
        raise ValueError("original pixel review source changed")
    if pixels.get("reviewer") in (None, "") or pixels.get("diagnostic_fixture") is not False:
        raise ValueError("original pixel review lacks independent reviewer")
    observations = pixels.get("observations", {})
    for key in PIXELS:
        item = observations.get(key, {})
        frame = item.get("frame")
        if (item.get("visible") is not True or not isinstance(frame, int)
                or not 0 <= frame < len(rows)
                or item.get("view") not in ("overview", "approach", "reference_corner", "driver_reference")
                or not item.get("description")):
            raise ValueError("actual pixels unverified: " + key)
    return {"format": "worker-delivery-audit", "passed": True, "case_id": case_id,
            "checks": {key: True for key in CHECKS}, "frames": len(rows),
            "video": "raw.mkv", "video_sha256": sha(video),
            "trace": "traffic_spec/trace.json", "trace_sha256": sha(trace),
            "frame_map_sha256": sha(mapping), "pixel_review_sha256": pixels.get("_file_sha256"),
            "physical_receipt_sha256": physical.get("_file_sha256")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=CASES)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--map", type=Path, required=True)
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--composition-receipt", type=Path, required=True)
    parser.add_argument("--decode-receipt", type=Path, required=True)
    parser.add_argument("--media-auditor", type=Path, required=True)
    parser.add_argument("--physical-receipt", type=Path, required=True)
    parser.add_argument("--pixel-review", type=Path, required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--attempt-number", type=int, required=True)
    parser.add_argument("--recording-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    case_id = ASSIGNMENT + "__" + args.case
    if args.case_id != case_id:
        raise ValueError("independent audit case identity differs")
    if args.physical_receipt.resolve() != (args.attempt / "result.json").resolve():
        raise ValueError("physical receipt must be the sealed Native result")
    source = audit_source_chain(args.attempt, args.case, args.map, args.layout)
    motion_consistency = check_motion_consistency(args.attempt, args.case,
                                                  args.map, args.layout)
    decode = verify_decode_receipt(source, args.attempt, args.decode_receipt,
                                   args.composition_receipt, args.media_auditor)
    physical = read(args.physical_receipt)
    physical["_file_sha256"] = sha(args.physical_receipt)
    pixels = read(args.pixel_review)
    pixels["_file_sha256"] = sha(args.pixel_review)
    core_path = args.attempt / "traffic_spec" / "trace.json"
    audit = verify_evidence(case_id, source, decode, physical, pixels,
                            read(core_path), args.attempt)
    audit["motion_consistency"] = motion_consistency
    audit.update(job_id=args.job_id, attempt=args.attempt_number,
                 recording_id=args.recording_id,
                 source_result_sha256=sha(args.attempt / "result.json"),
                 auditor_path=str(Path(__file__).resolve()), auditor_sha256=sha(Path(__file__)),
                 source_decode_receipt_path=str(args.decode_receipt.resolve()),
                 source_decode_receipt_sha256=sha(args.decode_receipt),
                 source_decode_auditor_sha256=sha(args.media_auditor))
    args.output.write_text(json.dumps(audit, indent=2) + "\n")
    print("independent original delivery audit passed: " + case_id)


if __name__ == "__main__":
    main()
