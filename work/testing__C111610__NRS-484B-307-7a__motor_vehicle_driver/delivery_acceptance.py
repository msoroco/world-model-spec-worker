"""Independent CPU review of saved arrow sources and diagnostic processing.

Production mode audits original PNG archives; diagnostic mode audits generated
four-view media and never claims physical or legal acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_camera_capture import CAMERAS
from saved_aspect import join_event_history
from saved_finalizer import ASSIGNMENT, SUFFIXES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(case, attempt, processed=None, diagnostic=False):
    attempt = Path(attempt).resolve()
    if case not in {ASSIGNMENT + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("unknown exact arrow case")
    site_path = attempt / "site.json"
    if not site_path.is_file():
        raise ValueError("saved delivery site source missing")
    site = json.loads(site_path.read_text())
    if site.get("case_id") != case:
        raise ValueError("saved delivery site selects another case")
    config = json.loads((attempt / "config.json").read_text())
    if config.get("selected_case_id") != case or set(config["cameras"]) != set(CAMERAS):
        raise ValueError("saved delivery configuration differs")
    event_receipt = json.loads((attempt / "arrow-event-receipt.json").read_text())
    if event_receipt.get("diagnostic") is not diagnostic:
        raise ValueError("event provenance differs")
    events = join_event_history(site, attempt, event_receipt["event_ref"], delivery=not diagnostic)
    if diagnostic:
        from worker_exchange.media import audit as decode
        mapping_sha = sha(attempt / "video_frames.jsonl")
        views = {name: decode(attempt / (name + ".mkv"), events["frame_count"],
                              mapping_sha256=mapping_sha) for name in CAMERAS}
        if processed is None:
            raise ValueError("diagnostic saved processing receipt required")
        version = Path(processed).resolve()
        receipt = json.loads((version / "processing.json").read_text())
        result = json.loads((version / "analysis/result.json").read_text())
        if (receipt.get("case_id") != case or receipt.get("passed") is not True or
                receipt.get("originals_preserved") is not True or
                receipt.get("timestamp_joins", {}).get("passed") is not True or
                receipt.get("result_sha256") != sha(version / "analysis/result.json") or
                receipt.get("final_video_checks", {}).get("passed") is not True or
                result.get("case_id") != case or
                receipt.get("physical_acceptance_claimed") is not False or
                receipt.get("legal_acceptance_claimed") is not False):
            raise ValueError("saved processing result is incomplete or changed")
        for name, expected in receipt["original_source_hashes"].items():
            if sha(attempt / name) != expected:
                raise ValueError("original acquisition changed: " + name)
        if not all(view["passed"] for view in views.values()):
            raise ValueError("four-view original decode failed")
        count = events["frame_count"]
    else:
        from delivery_audit import audit as audit_native
        production = audit_native(attempt, case)
        count = production["frame_count"]
    return {"format": "c111610-independent-delivery-cpu-v1", "case_id": case,
            "software_checks_passed": True, "source_joined_frames": count,
            "original_site_sha256": sha(site_path),
            "original_events_sha256": events["original_event_sha256"],
            "original_aspect_sha256": events["original_aspect_sha256"],
            "four_camera_decoded": True, "saved_processing_verified": bool(processed),
            "diagnostic": diagnostic, "physical_acceptance": False,
            "legal_verdict": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--processed")
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.case, args.attempt, args.processed, args.diagnostic), indent=2))


if __name__ == "__main__":
    main()
