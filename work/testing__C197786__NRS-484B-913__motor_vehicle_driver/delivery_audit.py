"""Standalone CPU audit of saved, sealed original-source hose packets.

This is a worker-side precheck. Local delivery acceptance still requires the
pinned source decoder, full video and physical-completion audit.
"""

import argparse
import hashlib
import json
from pathlib import Path

from fire_hose_delivery import compare_saved_hose, inspect_saved_hose


def verify_sources(packet, root):
    root = root.resolve()
    for key in ("hose", "road", "incident", "command_official", "consent", "vehicle"):
        binding = packet[key]
        path = (root / binding["source_path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"{key} original source file missing or outside root")
        if hashlib.sha256(path.read_bytes()).hexdigest() != binding["sha256"]:
            raise ValueError(f"{key} original source hash mismatch")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--variable", choices=("consent", "protection", "passage", "incident_purpose"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    packet = json.loads(args.packet.read_text())
    result = {"case_id": args.case_id, "observed": inspect_saved_hose(packet, args.case_id)}
    verify_sources(packet, args.source_root)
    if args.compare:
        if not args.variable:
            parser.error("--variable is required with --compare")
        other = json.loads(args.compare.read_text())
        result["comparison"] = compare_saved_hose(packet, other, args.variable)
        verify_sources(other, args.source_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
