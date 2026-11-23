"""Independent source-bound acceptance gate for one original median-crossing attempt."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("c125714_source_audit", ROOT / "delivery_audit.py")
SOURCE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(SOURCE)

SUFFIXES = ("precedence", "advance", "other_later", "opposite_straight",
            "opposite_intends_left", "opposite_makes_left", "wide_same_crossing")
CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")
MANEUVER_SOURCES = {"ego-body-history.jsonl", "intersection-context.json",
                    "video_frames.jsonl"}
OBSERVATIONS = ("ego", "other", "crossing", "device_context", "maneuver")
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def verify_case_binding(case_id: str, attempt: Path) -> dict:
    """Require the selected case in both sealed construction and config bytes."""
    attempt = Path(attempt).resolve()
    seal = read(attempt / "capture-seal.json")
    sources = seal.get("sources", {})
    for name in ("construction.json", "config.json"):
        path = attempt / name
        if not path.is_file() or sources.get(name) != sha(path):
            raise ValueError("sealed selected-case source missing or changed: " + name)
    construction = read(attempt / "construction.json")
    config = read(attempt / "config.json")
    if (construction.get("case_id") != case_id or
            config.get("selected_case_id") != case_id):
        raise ValueError("sealed construction/config selected another exact case")
    return {"construction_sha256": sources["construction.json"],
            "config_sha256": sources["config.json"]}


def verify_inputs(case_id: str, source: dict, physical: dict, pixels: dict,
                  decode: dict, core: dict, attempt: Path) -> dict:
    """Rejoin physical and human observations to original captured bytes."""
    attempt = Path(attempt).resolve()
    if case_id not in {ROOT.name + "__" + name for name in SUFFIXES}:
        raise ValueError("unknown exact case")
    if source.get("diagnostic_fixture") is not False or not {
            "ego-body-history.jsonl", "other-body-history.jsonl", "video_frames.jsonl",
            "road.xodr", "intersection-context.json",
            *SOURCE.CAMERAS} <= set(source.get("source_hashes", {})):
        raise ValueError("original Native participants and cameras unverified")
    for name, digest in source["source_hashes"].items():
        if sha(attempt / name) != digest:
            raise ValueError("original Native source changed: " + name)
    physical_checks = physical.get("physical_checks", {})
    if (physical.get("case_id") != case_id or
            physical.get("provenance_kind") != "native" or
            physical.get("diagnostic_fixture") is not False or
            not physical.get("setup_confirmed") or
            not physical.get("maneuver_completed") or
            not {"setup", "target", "maneuver"} <= set(physical_checks) or
            any(check.get("status") != "met" for check in physical_checks.values())):
        raise ValueError("physical completion unverified")
    for check in physical_checks.values():
        sources = check.get("sources", {})
        if not sources:
            raise ValueError("physical completion source bindings missing")
        for name, digest in sources.items():
            path = (attempt / name).resolve()
            if not path.is_relative_to(attempt) or not path.is_file() or sha(path) != digest:
                raise ValueError("physical completion source changed: " + name)
    maneuver_sources = physical_checks["maneuver"].get("sources", {})
    if (not MANEUVER_SOURCES <= set(maneuver_sources) or
            any(maneuver_sources[name] != source["source_hashes"][name]
                for name in MANEUVER_SOURCES)):
        raise ValueError("physical maneuver lacks sealed crossing source bindings")
    video = attempt / "raw.mkv"
    mapping = attempt / "video_frames.jsonl"
    trace = attempt / "traffic_spec" / "trace.json"
    if (decode.get("format") != "source-decode" or decode.get("passed") is not True or
            decode.get("video_sha256") != sha(video) or
            decode.get("mapping_sha256") != sha(mapping) or
            decode.get("checks", {}).get("frame_count") != "all-decoded-frames"):
        raise ValueError("full composed video decode unverified")
    scenes = core.get("scenes")
    frames = [json.loads(line) for line in mapping.read_text().splitlines()]
    if (not isinstance(scenes, list) or not frames or len(scenes) != len(frames)
            or decode.get("frames") != len(frames)):
        raise ValueError("Core trace and original frame count differ")
    for index, (scene, frame) in enumerate(zip(scenes, frames)):
        if frame.get("video_frame") != index or scene.get("t") != round(frame["time_s"] * 1000):
            raise ValueError("Core trace and original frame time join differs")
    if (pixels.get("format") != "worker-original-pixel-review" or
            pixels.get("case_id") != case_id or
            pixels.get("diagnostic_fixture") is not False or not pixels.get("reviewer") or
            pixels.get("video_sha256") != sha(video) or
            pixels.get("frame_map_sha256") != sha(mapping) or
            pixels.get("core_trace_sha256") != sha(trace)):
        raise ValueError("original pixel review missing or stale")
    for key in OBSERVATIONS:
        item = pixels.get("observations", {}).get(key, {})
        index = item.get("frame")
        if (item.get("visible") is not True or type(index) is not int or
                not 0 <= index < len(frames) or item.get("view") not in VIEWS or
                not item.get("description")):
            raise ValueError("actual pixels unverified: " + key)
    return {"format": "worker-delivery-audit", "passed": True, "case_id": case_id,
            "checks": {name: True for name in CHECKS}, "frames": len(frames),
            "video": "raw.mkv", "video_sha256": sha(video),
            "trace": "traffic_spec/trace.json", "trace_sha256": sha(trace),
            "frame_map_sha256": sha(mapping)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--physical-receipt", type=Path, required=True)
    parser.add_argument("--pixel-review", type=Path, required=True)
    parser.add_argument("--decode-receipt", type=Path, required=True)
    parser.add_argument("--media-auditor", type=Path, required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--attempt-number", type=int, required=True)
    parser.add_argument("--recording-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.case_id not in {ROOT.name + "__" + name for name in SUFFIXES}:
        raise ValueError("unknown exact case")
    if args.physical_receipt.resolve() != (args.attempt / "result.json").resolve():
        raise ValueError("physical receipt must be the sealed Native result")
    case_binding = verify_case_binding(args.case_id, args.attempt)
    source = SOURCE.audit_attempt(args.attempt)
    decode = read(args.decode_receipt)
    if decode.get("auditor_sha256") != sha(args.media_auditor):
        raise ValueError("full decode auditor revision changed")
    audit = verify_inputs(args.case_id, source, read(args.physical_receipt),
                          read(args.pixel_review), decode,
                          read(args.attempt / "traffic_spec" / "trace.json"), args.attempt)
    auditor = Path(__file__).resolve()
    audit.update(job_id=args.job_id, attempt=args.attempt_number,
                 recording_id=args.recording_id,
                 selected_case_source_hashes=case_binding,
                 source_result_sha256=sha(args.physical_receipt),
                 auditor_path=str(auditor), auditor_sha256=sha(auditor),
                 source_decode_receipt_path=str(args.decode_receipt.resolve()),
                 source_decode_receipt_sha256=sha(args.decode_receipt),
                 source_decode_auditor_sha256=sha(args.media_auditor),
                 pixel_review_sha256=sha(args.pixel_review))
    args.output.write_text(json.dumps(audit, indent=2) + "\n")
    print("original independent delivery audit passed: " + args.case_id)


if __name__ == "__main__":
    main()
