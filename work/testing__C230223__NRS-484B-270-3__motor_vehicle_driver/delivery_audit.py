"""Independent NRS 484B.270(3) delivery audit for saved Native attempts.

The diagnostic path tests this auditor without claiming original pixels or motion.
The local operator supplies reviewed original hashes and pixel observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from cycle_lane_2703 import VIEWS
from cycle_lane_source_audit import audit as audit_original


def read(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("delivery source missing or linked: " + str(path))
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _saved(attempt: Path, processing_path: Path, case_id: str) -> tuple[dict, dict]:
    receipt = read(processing_path)
    if (receipt.get("format") != "worker-saved-processing" or
            receipt.get("passed") is not True or
            receipt.get("recorded_only") is not True or
            receipt.get("originals_preserved") is not True or
            receipt.get("missing_evidence") is not False or
            receipt.get("case_id") != case_id):
        raise ValueError("complete saved-only processing receipt required")
    for relative, checksum in receipt.get("original_source_hashes", {}).items():
        path = (attempt / relative).resolve()
        if not path.is_relative_to(attempt) or not path.is_file() or sha(path) != checksum:
            raise ValueError("saved original changed: " + relative)
    result_path = Path(receipt["result"]).resolve()
    if sha(result_path) != receipt.get("result_sha256"):
        raise ValueError("saved result changed")
    result = read(result_path)
    if result.get("case_id") != case_id:
        raise ValueError("saved result belongs to another case")
    if (receipt.get("timestamp_joins", {}).get("frames") != 900 or
            receipt.get("timestamp_joins", {}).get("passed") is not True):
        raise ValueError("saved original frame/time joins incomplete")
    return receipt, result


def diagnostic(attempt: Path, processing_path: Path, case_id: str) -> dict:
    receipt, result = _saved(attempt, processing_path, case_id)
    provenance = read(attempt / "acquisition-provenance.json")
    if (provenance.get("provenance_kind") != "synthetic_fixture" or
            provenance.get("diagnostic_fixture") is not True or
            result.get("diagnostic_fixture") is not True or
            not receipt.get("final_video_checks", {}).get("passed")):
        raise ValueError("selected diagnostic software proof incomplete")
    return {"format": "cycle-lane-2703-delivery-audit-diagnostic-v1",
            "case_id": case_id, "recorded_only": True,
            "originals_preserved": True, "joined_frames": 900,
            "full_final_decode": True, "diagnostic_fixture": True,
            "native_source": False, "actual_pixels": False,
            "physical_completion": False, "legal_verdict": None}


def original(attempt: Path, processing_path: Path, case_id: str,
             review_path: Path, pixel_review_path: Path,
             video_relative: str, trace_relative: str,
             decode_receipt: Path, auditor_path: Path,
             job_id: str, attempt_number: int, recording_id: str) -> dict:
    receipt, result = _saved(attempt, processing_path, case_id)
    provenance = read(attempt / "acquisition-provenance.json")
    if (provenance.get("provenance_kind") != "native" or
            provenance.get("diagnostic_fixture") is not False or
            result.get("diagnostic_fixture") is not False):
        raise ValueError("original Native cycle-lane attempt required")
    if (not read(attempt / "capture-seal.json").get("events") ==
            ["capture_finished", "encoders_closed", "restoration_verified"] or
            read(attempt / "native-exit.json").get("event") != "native_exit" or
            read(attempt / "owner-release.json").get("operator_attested") is not True):
        raise ValueError("Native exit and owner release required")
    review = read(review_path)
    independent = audit_original(attempt, review["source_hashes"], case_id)
    pixel = read(pixel_review_path)
    if (pixel.get("case_id") != case_id or
            pixel.get("attempt_source_sha256") != independent["attempt_source_sha256"] or
            pixel.get("reviewer") in (None, "") or not pixel.get("method") or
            set(pixel.get("views", {})) != set(VIEWS)):
        raise ValueError("independent original pixel review absent or stale")
    for name in VIEWS:
        observation = pixel["views"][name]
        if (observation.get("video_sha256") != independent["media"][name]["sha256"] or
                observation.get("motorist_visible") is not True or
                observation.get("road_user_visible") is not True or
                not observation.get("reviewed_frames") or
                not observation.get("visibility_method")):
            raise ValueError("original pixels or required actor missing: " + name)
    if (result.get("physical_checks", {}).get("maneuver", {}).get("status") != "met" or
            result.get("maneuver_completed") is not True or
            result.get("measured_values", {}).get("frame_count") != 900):
        raise ValueError("physical completion lacks measured original evidence")
    video = (attempt / video_relative).resolve()
    trace = (attempt / trace_relative).resolve()
    if (not video.is_relative_to(attempt) or not trace.is_relative_to(attempt) or
            not video.is_file() or not trace.is_file()):
        raise ValueError("canonical video or Core trace escapes original attempt")
    from worker_exchange.media import audit as decode
    decoded = decode(video, 900, mapping_sha256=sha(attempt / "video_frames.jsonl"),
                     receipt=decode_receipt)
    scenes = read(trace).get("scenes", [])
    if len(scenes) != 900 or decoded.get("passed") is not True:
        raise ValueError("full original video/Core decode incomplete")
    if auditor_path.resolve() != Path(__file__).resolve():
        raise ValueError("auditor source path differs")
    return {"format": "worker-delivery-audit", "passed": True,
            "case_id": case_id, "job_id": job_id, "attempt": attempt_number,
            "recording_id": recording_id, "checks": {
                "native_source": True, "all_participants": True,
                "time_join": True, "full_video_decode": True,
                "actual_pixels": True, "physical_completion": True},
            "source_result_sha256": sha(attempt / "result.json"),
            "video": video_relative, "video_sha256": sha(video),
            "trace": trace_relative, "trace_sha256": sha(trace),
            "frames": 900, "auditor_path": str(auditor_path.resolve()),
            "auditor_sha256": sha(auditor_path),
            "source_decode_receipt_path": str(decode_receipt.resolve()),
            "source_decode_receipt_sha256": sha(decode_receipt),
            "source_decode_auditor_sha256": decoded["auditor_sha256"],
            "originals_preserved": receipt["originals_preserved"],
            "pixel_review_sha256": sha(pixel_review_path),
            "physical_acceptance_claimed": False, "legal_verdict": None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--processing", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--review", type=Path)
    parser.add_argument("--pixel-review", type=Path)
    parser.add_argument("--video")
    parser.add_argument("--trace")
    parser.add_argument("--decode-receipt", type=Path)
    parser.add_argument("--auditor", type=Path)
    parser.add_argument("--job")
    parser.add_argument("--attempt-number", type=int)
    parser.add_argument("--recording-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    attempt = args.attempt.resolve()
    if args.diagnostic:
        value = diagnostic(attempt, args.processing, args.case)
    else:
        required = (args.review, args.pixel_review, args.video, args.trace,
                    args.decode_receipt, args.auditor, args.job,
                    args.attempt_number, args.recording_id)
        if any(item is None for item in required):
            raise ValueError("original independent audit inputs required")
        value = original(attempt, args.processing, args.case,
                         args.review, args.pixel_review, args.video, args.trace,
                         args.decode_receipt, args.auditor, args.job,
                         args.attempt_number, args.recording_id)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps(value, sort_keys=True))


if __name__ == "__main__":
    main()
