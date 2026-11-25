"""Independent source audit for the bicycle device and officer delivery.

This checker never derives official authority or pixel visibility from an
expected label. Production acceptance additionally needs an original review
packet tied to the exact captured bytes and a separate source decode receipt.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from native_device import read_site
from saved_camera_audit import audit as audit_cameras
from saved_instruction import measure

CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_attempt_sources(attempt: Path, case: dict) -> dict:
    """Check the complete sealed original acquisition before any case review."""
    root = Path(attempt)
    if (root / "fixture-provenance.json").exists():
        raise ValueError("diagnostic fixture cannot satisfy original attempt audit")
    from worker_exchange.media import audit as audit_video
    source_hashes = json.loads((root / "original-source-hashes.json").read_text())
    site_path = root / "original-site.json"
    trace_path = root / "original-instruction-trace.json"
    if source_hashes.get("site") != sha(site_path):
        raise ValueError("original site source manifest changed")
    site = read_site(site_path, source_hashes["site"])
    if site["device_type"] != case["device_type"]:
        raise ValueError("original device type differs from selected case")
    if case["officer_direction"] != "none":
        if source_hashes.get("officer") != sha(root / "original-officer.json"):
            raise ValueError("original officer source manifest changed")
    elif "officer" in source_hashes:
        raise ValueError("undeclared original officer source")
    trace_sha = sha(trace_path)
    packet = json.loads(trace_path.read_text())
    if packet.get("diagnostic_fixture") is True:
        raise ValueError("diagnostic trace cannot satisfy original attempt audit")
    instruction = measure(trace_path, trace_sha, case, site, source_hashes["site"])
    cameras = audit_cameras(trace_path, trace_sha, case["case_id"])
    rows = packet["samples"]
    mapping = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
    trace = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
    if len(rows) != len(mapping) or len(trace) != len(rows):
        raise ValueError("original frame count or trace join differs")
    for index, (row, frame, state) in enumerate(zip(rows, mapping, trace)):
        if (frame.get("video_frame") != index or frame.get("carla_frame") != row["frame"]
                or state.get("frame") != row["frame"]
                or not math.isclose(frame.get("time_s", math.inf), row["time_s"], abs_tol=1e-4)
                or not math.isclose(state.get("time_s", math.inf), row["time_s"], abs_tol=1e-4)):
            raise ValueError("original frame or time identity differs")
    acquisition = json.loads((root / "acquisition.json").read_text())
    required = ("original-site.json", "original-instruction-trace.json",
                "original-source-hashes.json", "trace.jsonl", "video_frames.jsonl",
                "body_history.jsonl", "overview.mkv", "approach.mkv",
                "reference_corner.mkv", "driver_reference.mkv")
    for name in required:
        if acquisition.get(name, {}).get("sha256") != sha(root / name):
            raise ValueError("missing or stale original acquisition source: " + name)
    videos = {}
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        source = root / (name + ".mkv")
        decoded = audit_video(source, len(rows), mapping_sha256=sha(root / "video_frames.jsonl"))
        if decoded.get("passed") is not True:
            raise ValueError("full original video decode failed: " + name)
        videos[name] = {"sha256": sha(source), "frames": decoded["frames"]}
    config = json.loads((root / "config.json").read_text())
    if config.get("selected_case_id") != case["case_id"]:
        raise ValueError("exact original case configuration differs")
    seal = json.loads((root / "capture-seal.json").read_text())
    if (seal.get("format") != "worker-sealed-capture" or
            seal.get("provenance_kind") != "native" or
            seal.get("frames") != len(rows) or
            seal.get("restoration", {}).get("restored") is not True):
        raise ValueError("original capture seal or restoration differs")
    for name, expected in seal.get("sources", {}).items():
        if sha(root / name) != expected:
            raise ValueError("sealed original source changed: " + name)
    return {"site_path": site_path, "site_sha256": source_hashes["site"],
            "trace_path": trace_path, "trace_sha256": trace_sha,
            "instruction": instruction, "cameras": cameras, "videos": videos,
            "frame_count": len(rows)}


def audit_attempt(attempt: Path, case: dict, review_path: Path,
                  review_sha256: str) -> dict:
    sources = audit_attempt_sources(attempt, case)
    receipt = audit(case, sources["site_path"], sources["site_sha256"],
                    sources["trace_path"], sources["trace_sha256"],
                    review_path=review_path, review_sha256=review_sha256)
    receipt["original_attempt_sources"] = {key: sources[key] for key in
                                           ("frame_count", "videos")}
    return receipt


def audit(case: dict, site_path: Path, site_sha256: str, trace_path: Path,
          trace_sha256: str, *, diagnostic: bool = False,
          review_path: Path | None = None, review_sha256: str | None = None) -> dict:
    site = read_site(Path(site_path), site_sha256, allow_diagnostic=diagnostic)
    if site["device_type"] != case["device_type"]:
        raise ValueError("governing device type differs from selected case")
    trace = Path(trace_path)
    if not diagnostic and json.loads(trace.read_text()).get("diagnostic_fixture") is True:
        raise ValueError("Diagnostic source cannot satisfy delivery audit")
    instruction = measure(trace, trace_sha256, case, site, site_sha256)
    cameras = audit_cameras(trace, trace_sha256, case["case_id"])
    if cameras["decoded_frames"] != instruction["frame_count"]:
        raise ValueError("source frame and camera join differs")
    evidence = {"site": site_sha256, "trace": trace_sha256,
                "cameras": {name: ref["sha256"] for name, ref in
                            json.loads(trace.read_text())["camera_sources"].items()}}
    receipt = {
        "format": "worker-delivery-audit", "case_id": case["case_id"],
        "checks": list(CHECKS), "source_hashes": evidence,
        "instruction_measurement": instruction,
        "source_decode": cameras, "physical_acceptance": False,
        "legal_assessment": "unresolved", "diagnostic_fixture": bool(diagnostic),
    }
    if diagnostic:
        return receipt
    if review_path is None or not review_sha256:
        raise ValueError("Original independent physical and pixel review required")
    if sha(review_path) != review_sha256:
        raise ValueError("original independent review hash mismatch")
    review = json.loads(review_path.read_text())
    if review.get("source_kind") != "original_independent_delivery_review":
        raise ValueError("unverified independent review source")
    if review.get("case_id") != case["case_id"] or review.get("source_hashes") != evidence:
        raise ValueError("independent review source binding differs")
    if review.get("physical_completion") is not True or review.get("actual_pixels") is not True:
        raise ValueError("physical completion or actual pixel review absent")
    if review.get("full_video_decode") is not True or review.get("all_participants") is not True:
        raise ValueError("independent participant or decode review absent")
    receipt["independent_review_sha256"] = review_sha256
    receipt["physical_acceptance"] = True
    return receipt


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--site", type=Path)
    parser.add_argument("--site-sha256")
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--trace-sha256")
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--review", type=Path)
    parser.add_argument("--review-sha256")
    parser.add_argument("--attempt", type=Path)
    args = parser.parse_args()
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    cases = [row for row in plan["cases"] if row["case_id"] == args.case]
    if len(cases) != 1:
        raise ValueError("unknown exact delivery case")
    if args.attempt:
        if args.diagnostic or args.review is None or not args.review_sha256:
            raise ValueError("original attempt audit requires independent review and hash")
        result = audit_attempt(args.attempt, cases[0], args.review, args.review_sha256)
    else:
        if not all((args.site, args.site_sha256, args.trace, args.trace_sha256)):
            raise ValueError("explicit source paths and hashes required")
        result = audit(cases[0], args.site, args.site_sha256, args.trace,
                       args.trace_sha256, diagnostic=args.diagnostic,
                       review_path=args.review, review_sha256=args.review_sha256)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
