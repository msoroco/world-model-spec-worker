"""Standalone CPU audit of saved, sealed original-source hose packets.

This is a worker-side precheck. Local delivery acceptance still requires the
pinned source decoder, full video and physical-completion audit.
"""

import argparse
import hashlib
import json
from pathlib import Path

from fire_hose_delivery import body_over_hose_frames, compare_saved_hose, inspect_saved_hose


def verify_sources(packet, root):
    root = root.resolve()
    for key in ("hose", "road", "incident", "command_official", "consent", "vehicle"):
        binding = packet[key]
        path = (root / binding["source_path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"{key} original source file missing or outside root")
        if hashlib.sha256(path.read_bytes()).hexdigest() != binding["sha256"]:
            raise ValueError(f"{key} original source hash mismatch")


def verify_native_frames(packet, root):
    """Join the complete measured history to a saved original JSONL source."""
    root = root.resolve()
    native = packet.get("native", {})
    if not native.get("source_path") or not native.get("source_sha256"):
        raise ValueError("Native original frame source binding missing")
    path = (root / native["source_path"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Native original frame source file missing or outside root")
    if hashlib.sha256(path.read_bytes()).hexdigest() != native["source_sha256"]:
        raise ValueError("Native original frame source hash mismatch")
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if rows != native.get("frames"):
        raise ValueError("Native original frame source content mismatch")
    seal_path = root / "seal.json"
    if not seal_path.is_file() or hashlib.sha256(seal_path.read_bytes()).hexdigest() != native.get("result_sha256"):
        raise ValueError("sealed Native result source hash mismatch")
    seal = json.loads(seal_path.read_text())
    if (seal.get("case_id") != packet.get("case_id") or
            seal.get("frame_count") != len(rows) or
            seal.get("frames_sha256") != native["source_sha256"] or
            seal.get("rate_hz") != 20 or
            seal.get("physical_completion") != "unreviewed"):
        raise ValueError("sealed Native frame identity or profile mismatch")


def verify_original_context(packet, root):
    """Join every claimed physical/command fact to its distinct source JSON."""
    root = root.resolve()
    paths = set()
    for key in ("hose", "road", "incident", "command_official", "consent", "vehicle"):
        binding = packet[key]
        path = (root / binding["source_path"]).resolve()
        if path in paths:
            raise ValueError("distinct original context sources required")
        paths.add(path)
        original = json.loads(path.read_text())
        claimed = {name: value for name, value in binding.items()
                   if name not in ("source_path", "sha256")}
        if key == "road" and "owner" in claimed:
            if claimed.get("private_way_owner") != claimed.get("owner"):
                raise ValueError("private way owner alias differs from original source")
            claimed.pop("private_way_owner", None)
        if original != claimed:
            raise ValueError(f"{key} original source content mismatch")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--variable", choices=("consent", "protection", "passage", "incident_purpose"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-complete-body", action="store_true")
    parser.add_argument("--expected-passage", choices=("cross", "avoid"))
    parser.add_argument("--compare-expected-passage", choices=("cross", "avoid"))
    args = parser.parse_args()
    packet = json.loads(args.packet.read_text())
    result = {"case_id": args.case_id, "observed": inspect_saved_hose(packet, args.case_id)}
    verify_sources(packet, args.source_root)
    if args.require_complete_body:
        if not args.expected_passage:
            parser.error("--expected-passage is required with --require-complete-body")
        verify_native_frames(packet, args.source_root)
        verify_original_context(packet, args.source_root)
        hits = body_over_hose_frames(packet, args.case_id)
        if bool(hits) != (args.expected_passage == "cross"):
            raise ValueError("observed original body passage differs from exact case")
        result["physical_completion"] = {"original_body_contact_frames": hits,
                                         "expected_passage": args.expected_passage,
                                         "complete_original_frame_history": True,
                                         "legal_verdict": None}
    if args.compare:
        if not args.variable:
            parser.error("--variable is required with --compare")
        other = json.loads(args.compare.read_text())
        verify_sources(other, args.source_root)
        if args.require_complete_body:
            if not args.compare_expected_passage:
                parser.error("--compare-expected-passage required with complete comparison")
            verify_native_frames(other, args.source_root)
            verify_original_context(other, args.source_root)
            other_hits = body_over_hose_frames(other, other["case_id"])
            if bool(other_hits) != (args.compare_expected_passage == "cross"):
                raise ValueError("compared original body passage differs from exact case")
            if args.variable == "passage" and bool(hits) == bool(other_hits):
                raise ValueError("original body-passage contrast absent")
        result["comparison"] = compare_saved_hose(packet, other, args.variable)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
