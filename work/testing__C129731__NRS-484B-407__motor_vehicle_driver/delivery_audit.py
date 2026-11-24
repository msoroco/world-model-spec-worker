"""Independent selected-reuse review of original archived delivery evidence.

Even a matching archived acceptance does not establish NRS 484B.407 driver
visibility. This reports source review, not a new canonical acceptance.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review(plan: dict, repository: Path, attempt: Path, acquired: Path,
           decode_receipt: Path) -> dict:
    from selected_media_audit import audit_acquired
    repository = Path(repository).resolve()
    worker_root = Path(__file__).resolve().parents[2]
    output = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    if not output.is_relative_to(worker_root / ".runtime-work"):
        raise ValueError("pipeline output root must be under .runtime-work")
    selected = audit_acquired(plan, repository, attempt, acquired)
    receipt = json.loads((Path(acquired) / "acquisition.json").read_text())
    rel = Path(receipt["metadata_path"])
    meta_path = (repository / rel).resolve()
    if rel.is_absolute() or not meta_path.is_relative_to(repository) or \
            _sha(meta_path) != receipt["metadata_sha256"]:
        raise ValueError("frozen metadata changed after acquisition")
    metadata = json.loads(meta_path.read_text())
    archive_path = Path(metadata.get("acceptance", {}).get("delivery_audit", ""))
    if (not archive_path.is_absolute() or selected["recording_id"] not in archive_path.parts or
            not archive_path.is_file()):
        raise ValueError("original archived delivery audit missing")
    archive_sha = metadata.get("acceptance", {}).get("delivery_audit_sha256")
    if _sha(archive_path) != archive_sha:
        raise ValueError("original archived delivery audit hash mismatch")
    archived = json.loads(archive_path.read_text())
    if (archived.get("format") != "worker-delivery-audit" or archived.get("passed") is not True or
            archived.get("case_id") != selected["case_id"] or
            archived.get("recording_id") != selected["recording_id"] or
            archived.get("job_id") != metadata.get("job_id") or
            archived.get("attempt") != metadata.get("attempt") or
            archived.get("frames") != 900 or
            archived.get("video_sha256") != selected["video_sha256"] or
            archived.get("trace_sha256") != selected["trace_sha256"] or
            any(archived.get("checks", {}).get(name) is not True for name in CHECKS)):
        raise ValueError("original archived delivery evidence does not match selected source")
    sys.path.insert(0, str(worker_root / "runtime" / "scenario_pipeline"))
    from worker_exchange.media import verify_receipt
    checker = _sha(Path(__file__).with_name("saved_media_decode.py"))
    source_decode = verify_receipt(Path(acquired) / "raw.mkv", decode_receipt, 900,
                                   mapping_sha256=selected["frame_map_sha256"],
                                   required_checks={"pixel_presence": checker})
    return {"format": "c129731-selected-original-delivery-review-v1",
            "case_id": selected["case_id"], "recording_id": selected["recording_id"],
            "original_archived_audit_sha256": archive_sha,
            "source_decode_receipt_sha256": _sha(Path(decode_receipt)),
            "source_decode_auditor_sha256": source_decode["auditor_sha256"],
            "frame_map_sha256": selected["frame_map_sha256"],
            "video_sha256": selected["video_sha256"],
            "trace_sha256": selected["trace_sha256"],
            "archived_original_checks": {name: True for name in CHECKS},
            "law_specific_visibility_review": "unresolved",
            "canonical_acceptance": "not_performed_here"}


def audit_delivery(attempt: Path, case_id: str, job_id: str, attempt_number: int,
                   recording_id: str, decode_receipt: Path, *, cpu_test: bool = False) -> dict:
    """Inspect exact saved bytes for local delivery; CPU tests never claim acceptance."""
    attempt = Path(attempt).resolve()
    decode_receipt = Path(decode_receipt).resolve()
    if decode_receipt.exists():
        raise ValueError("source decode receipt already exists")
    runtime_roots = [parent / "runtime/scenario_pipeline"
                     for parent in Path(__file__).resolve().parents]
    runtime_roots = [path for path in runtime_roots if path.is_dir()]
    if runtime_roots:
        sys.path.insert(0, str(runtime_roots[0]))
    from worker_exchange.media import audit as decode
    from worker_exchange.native_output import validate_result
    from worker_exchange.common import read

    def pixel_presence(frame):
        pixels = frame.pixels
        if len(pixels) != frame.width * frame.height * 3 or len(set(pixels)) < 3:
            raise ValueError("decoded frame lacks actual varied pixels")

    result_path = attempt / "result.json"
    result = validate_result(read(result_path))
    if result.get("case_id") != case_id:
        raise ValueError("delivery result selects another case")
    video_rel = "event_review.webm"
    trace_rel = "converted/trace.json"
    video, trace, frame_map = (attempt / video_rel, attempt / trace_rel,
                               attempt / "video_frames.jsonl")
    for source in (video, trace, frame_map, attempt / "sight_rays.json",
                   attempt / "approach_motion.json", attempt / "ego_motion.json"):
        if not source.is_file():
            raise ValueError("missing delivery source: " + source.name)
    scenes = read(trace).get("scenes", [])
    mapping = [json.loads(line) for line in frame_map.read_text().splitlines() if line]
    if len(scenes) != 900 or len(mapping) != len(scenes):
        raise ValueError("delivery frame count differs from 900-frame contract")
    if any(row.get("video_frame") != index or scenes[index].get("t") !=
           round(row.get("time_s", -1) * 1000) for index, row in enumerate(mapping)):
        raise ValueError("original frame/Core timestamp join failed")
    approaches = read(attempt / "approach_motion.json").get("samples", [])
    ego = read(attempt / "ego_motion.json").get("samples", [])
    rays = read(attempt / "sight_rays.json").get("samples", [])
    directions = {row.get("direction") for row in rays}
    if (not approaches or not ego or
            not {"behind_same_direction", "ahead_opposing"} <= directions or
            any(not row.get("vehicle_id") for row in approaches)):
        raise ValueError("required participants or two-direction sight source missing")
    source_hashes = {}
    seal_path = attempt / "capture-seal.json"
    native = result.get("provenance_kind") == "native" and result.get("diagnostic_fixture") is False
    if native:
        if not seal_path.is_file() or not (attempt / "native-exit.json").is_file():
            raise ValueError("sealed Native exit missing")
        seal = read(seal_path)
        for name, checksum in seal.get("sources", {}).items():
            source = (attempt / name).resolve()
            if not source.is_relative_to(attempt) or _sha(source) != checksum:
                raise ValueError("sealed Native source changed: " + name)
            source_hashes[name] = checksum
    elif not cpu_test:
        raise ValueError("original Native source required for delivery audit")
    checker = _sha(Path(__file__))
    decoded = decode(video, len(scenes),
                     checkers={"pixel_presence": (checker, pixel_presence)},
                     mapping_sha256=_sha(frame_map), receipt=decode_receipt)
    statuses = result.get("physical_checks", {})
    physical = (statuses.get("setup", {}).get("status") == "met" and
                statuses.get("target", {}).get("status") == "met" and
                statuses.get("maneuver", {}).get("status") == "met")
    if not physical and not cpu_test:
        raise ValueError("physical completion not established by saved source")
    checks = {"native_source": native, "all_participants": True,
              "time_join": True, "full_video_decode": True,
              "actual_pixels": True, "physical_completion": physical}
    return {"format": "worker-delivery-audit", "passed": all(checks.values()),
            "cpu_test": cpu_test, "case_id": case_id, "job_id": job_id,
            "attempt": attempt_number, "recording_id": recording_id,
            "source_result_sha256": _sha(result_path), "frames": len(scenes),
            "video": video_rel, "video_sha256": _sha(video),
            "trace": trace_rel, "trace_sha256": _sha(trace),
            "checks": checks, "source_hashes": source_hashes,
            "auditor_path": str(Path(__file__).resolve()),
            "auditor_sha256": _sha(Path(__file__)),
            "source_decode_receipt_path": str(decode_receipt),
            "source_decode_receipt_sha256": _sha(decode_receipt),
            "source_decode_auditor_sha256": decoded["auditor_sha256"],
            "scope": "diagnostic software test only" if cpu_test else "original saved-source audit"}


def _main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--attempt-number", required=True, type=int)
    parser.add_argument("--recording", required=True)
    parser.add_argument("--decode-receipt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--cpu-test", action="store_true")
    args = parser.parse_args()
    value = audit_delivery(Path(args.attempt), args.case, args.job,
                           args.attempt_number, args.recording,
                           Path(args.decode_receipt), cpu_test=args.cpu_test)
    Path(args.output).write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps({"case_id": value["case_id"], "software_checks_passed":
                      all(value["checks"][name] for name in
                          ("all_participants", "time_join", "full_video_decode", "actual_pixels")),
                      "canonical_eligible": value["passed"]}))


if __name__ == "__main__":
    _main()
