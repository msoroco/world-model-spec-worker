"""Independent saved-source gate for the taxi stand delivery candidate.

This checks original bytes and frame identities. A passing source gate is not a
physical, pixel-visibility, document-authority, or legal acceptance decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from taxi_cameras import NAMES
from turn_trace_finalizer import ASSIGNMENT, finalize


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("missing or escaping original source: " + name)
    return path


def _rows(path: Path) -> list[dict]:
    try:
        rows = [json.loads(line) for line in path.read_text().splitlines()]
    except json.JSONDecodeError as exc:
        raise ValueError("invalid original frame map") from exc
    if not rows:
        raise ValueError("empty original frame map")
    return rows


def audit_source_chain(attempt: Path, case: str, map_path: Path,
                       layout_path: Path) -> dict:
    """Reject stale seals, missing streams, and partial/misaligned acquisition."""
    root = Path(attempt).resolve()
    if case not in ("near_stand", "far_stand") or not root.is_dir():
        raise ValueError("unknown case or missing attempt")
    trace = _source(root, "original-trace.jsonl")
    trace_seal = _source(root, "original-trace-seal.json")
    packet = _source(root, "reviewed-context.json")
    mapping_path = _source(root, "video_frames.jsonl")
    measurement = finalize(trace, trace_seal, packet, map_path, layout_path, root)
    if measurement["case_id"] != ASSIGNMENT + "__" + case:
        raise ValueError("measurement selected another case")
    motion = _rows(trace)
    mapping = _rows(mapping_path)
    if len(motion) != len(mapping):
        raise ValueError("original motion and frame map lengths differ")
    for index, (pose, frame) in enumerate(zip(motion, mapping)):
        if (frame.get("video_frame") != index or
                frame.get("carla_frame") != pose["frame"] or
                frame.get("native_frame") != pose["frame"] or
                not isinstance(frame.get("time_s"), (int, float)) or
                abs(frame["time_s"] - pose["time_s"]) > 1e-4):
            raise ValueError("original motion/frame-map identity differs")
    seal = json.loads(_source(root, "capture-seal.json").read_text())
    if (seal.get("format") != "worker-sealed-capture" or
            seal.get("provenance_kind") != "native" or
            seal.get("diagnostic_fixture") is not False or
            seal.get("frames") != len(mapping) or
            seal.get("restoration", {}).get("restored") is not True or
            seal.get("events") != ["capture_finished", "encoders_closed",
                                    "restoration_verified"] or
            seal.get("physical_acceptance_claimed") is not False):
        raise ValueError("Native capture seal incomplete or inconsistent")
    if set(seal.get("encoder_exit_codes", {})) != set(NAMES) or any(
            code != 0 for code in seal["encoder_exit_codes"].values()):
        raise ValueError("original camera encoders not all closed successfully")
    sources = seal.get("sources", {})
    required = ("original-trace.jsonl", "original-trace-seal.json",
                "reviewed-context.json", "video_frames.jsonl", "trace.jsonl",
                "taxi-controller-history.jsonl", "config.json", "construction.json",
                "runner.py", *(name + ".mkv" for name in NAMES))
    for name in required:
        if sources.get(name) != _sha(_source(root, name)):
            raise ValueError("Native capture seal source differs: " + name)
    for name in ("trace.jsonl", "taxi-controller-history.jsonl"):
        rows = _rows(_source(root, name))
        if len(rows) != len(mapping) or any(
                row.get("frame") != pose["frame"] or
                abs(row.get("time_s", float("inf")) - pose["time_s"]) > 1e-4
                for row, pose in zip(rows, motion)):
            raise ValueError("original acquisition frame join differs: " + name)
    if seal.get("native_revision", {}).get("construction_sha256") != sources["construction.json"] or seal["native_revision"].get("runner_sha256") != sources["runner.py"]:
        raise ValueError("Native revision differs from sealed construction")
    return {"format": "c150530-saved-source-audit-v1", "case_id": measurement["case_id"],
            "passed": True, "frames": len(mapping), "capture_seal_sha256": _sha(root / "capture-seal.json"),
            "frame_map_sha256": _sha(mapping_path), "trace_sha256": _sha(trace),
            "measurement": measurement,
            "source_hashes": {name: sources[name] for name in required},
            "physical_or_pixel_acceptance": False}


def verify_decode_receipt(source_audit: dict, attempt: Path, receipt: Path,
                          composition_receipt: Path, media_auditor: Path) -> dict:
    """Bind a complete decode receipt to the exact composed source and auditor."""
    root = Path(attempt).resolve()
    video = _source(root, "raw.mkv")
    composition = json.loads(Path(composition_receipt).read_text())
    if (composition.get("format") != "synchronized-four-view" or
            composition.get("sources") != {name: source_audit["source_hashes"][name + ".mkv"]
                                            for name in NAMES} or
            composition.get("frame_map_sha256") != source_audit["frame_map_sha256"] or
            composition.get("primary_sha256") != _sha(video) or
            composition.get("frames") != source_audit["frames"]):
        raise ValueError("composed video is not joined to four sealed sources")
    proof = json.loads(Path(receipt).read_text())
    if (proof.get("format") != "source-decode" or proof.get("passed") is not True or
            proof.get("video_sha256") != _sha(video) or
            proof.get("frames") != source_audit["frames"] or
            proof.get("mapping_sha256") != source_audit["frame_map_sha256"] or
            proof.get("auditor_sha256") != _sha(Path(media_auditor)) or
            proof.get("checks", {}).get("frame_count") != "all-decoded-frames"):
        raise ValueError("composed video has no current full-decode receipt")
    return {"format": "c150530-video-source-join-v1", "case_id": source_audit["case_id"],
            "passed": True, "video_sha256": _sha(video),
            "four_view_receipt_sha256": _sha(Path(composition_receipt)),
            "source_decode_receipt_sha256": _sha(Path(receipt)),
            "source_decode_auditor_sha256": _sha(Path(media_auditor)),
            "actual_pixels_reviewed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", choices=("near_stand", "far_stand"), required=True)
    parser.add_argument("--map", type=Path, required=True)
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--decode-receipt", type=Path, required=True)
    parser.add_argument("--composition-receipt", type=Path, required=True)
    parser.add_argument("--media-auditor", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    chain = audit_source_chain(args.attempt, args.case, args.map, args.layout)
    chain["video"] = verify_decode_receipt(chain, args.attempt, args.decode_receipt,
                                           args.composition_receipt, args.media_auditor)
    args.output.write_text(json.dumps(chain, indent=2) + "\n")


if __name__ == "__main__":
    main()
