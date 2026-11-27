"""Independent saved right-curb delivery audit; diagnostic evidence stays pending."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from audit_original_attempt import audit as audit_original


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def audit(attempt, processing, decode_receipt, case_id):
    attempt = Path(attempt)
    processing = Path(processing)
    decode_receipt = Path(decode_receipt)
    original = audit_original(attempt, case_id)
    config = read(attempt / "config.json")
    if config.get("selected_case_id") != case_id or config.get("law_id") != "NRS-484B-457-1":
        raise ValueError("saved right-curb case identity changed")
    rows = [json.loads(line) for line in (attempt / "trace.jsonl").read_text().splitlines() if line]
    video_map = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines() if line]
    native_map = read(attempt / "original-attempt/frame-map.json")["frames"]
    if not rows or not len(rows) == len(video_map) == len(native_map) == original["frame_count"]:
        raise ValueError("original wheel, trace and four-view frame counts differ")
    for index, (row, frame, native) in enumerate(zip(rows, video_map, native_map)):
        if (row.get("frame") != frame.get("carla_frame") or
                frame.get("carla_frame") != native.get("native_frame") or
                frame.get("video_frame") != index or
                abs(row.get("time_s", -1) - frame.get("time_s", -2)) > 1e-6 or
                abs(frame.get("time_s", -1) - native.get("native_time_s", -2)) > 1e-6):
            raise ValueError("original wheel, trace and camera time join differs")
    processed = read(processing)
    if (processed.get("format") != "worker-saved-processing" or processed.get("passed") is not True or
            processed.get("recorded_only") is not True or processed.get("originals_preserved") is not True or
            processed.get("case_id") != case_id):
        raise ValueError("saved-only processing receipt absent or failed")
    saved_result = Path(processed.get("result", ""))
    if not saved_result.is_file() or sha(saved_result) != processed.get("result_sha256"):
        raise ValueError("saved right-curb result missing or stale")
    result = read(saved_result)
    if result.get("case_id") != case_id or result.get("recording_description") != read(attempt / "construction.json")["recording_description"]:
        raise ValueError("saved right-curb result changed case or observation contract")
    from worker_exchange.media import verify_receipt
    stage = Path(processed["analysis_directory"])
    mapping_sha = sha(attempt / "video_frames.jsonl")
    source_receipts = []
    for index, name in enumerate(("overview", "approach", "reference_corner", "driver_reference")):
        receipt = stage.parent / ("source-%d.json" % index)
        decoded = verify_receipt(stage / (name + ".mkv"), receipt, len(rows),
                                 mapping_sha256=mapping_sha)
        source_receipts.append(sha(receipt))
        if decoded.get("passed") is not True or decoded.get("frames") != len(rows):
            raise ValueError("saved four-view pixels did not fully decode")
    decoded = read(decode_receipt)
    from worker_exchange import media
    if (decoded != processed.get("final_video_checks") or
            decoded.get("auditor_sha256") != sha(media.__file__) or
            decoded.get("passed") is not True or decoded.get("frames") != len(rows) or
            decoded.get("checks", {}).get("frame_count") != "all-decoded-frames"):
        raise ValueError("saved composite pixels did not fully decode")
    diagnostic = original["diagnostic_fixture"]
    lifecycle = False
    if not diagnostic:
        audit_original(attempt, case_id, require_native_attestation=True)
        seal = read(attempt / "capture-seal.json")
        native_exit = read(attempt / "native-exit.json")
        owner = read(attempt / "owner-release.json")
        if (seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"] or
                native_exit.get("capture_seal_sha256") != sha(attempt / "capture-seal.json") or
                owner.get("operator_attested") is not True or
                owner.get("native_exit_sha256") != sha(attempt / "native-exit.json")):
            raise ValueError("Native closure or owner release incomplete")
        lifecycle = True
    physical = result.get("physical_checks", {}).get("maneuver", {}).get("status") == "met"
    accepted = bool(not diagnostic and lifecycle and original["frame_count"] == 900 and
                    physical and result.get("setup_confirmed") is True and
                    result.get("behavior_attempted") is True and
                    result.get("maneuver_completed") is True and
                    all(check.get("matched") is True for check in result.get("target_checks", [])))
    return {"format": "worker-right-curb-delivery-audit", "case_id": case_id,
            "auditor_passed": True, "accepted_for_local_review": accepted,
            "diagnostic_fixture": diagnostic, "frame_count": len(rows),
            "original_source_audit": original["structural_status"],
            "saved_processing_sha256": sha(processing), "saved_result_sha256": sha(saved_result),
            "four_view_decode_sha256": source_receipts,
            "composite_decode_sha256": sha(decode_receipt),
            "physical_completion": physical, "native_lifecycle_complete": lifecycle,
            "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    for name in ("attempt", "processing", "decode-receipt", "case"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.processing, args.decode_receipt, args.case),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
