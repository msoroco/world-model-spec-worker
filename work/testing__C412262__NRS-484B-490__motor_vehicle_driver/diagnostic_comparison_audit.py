"""Independent isolation checks on bounded synthetic compatibility attempts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from comparison_audit import audit as audit_original
from diagnostic_delivery_audit import audit_diagnostic
from highway_scene_construction import ASSIGNMENT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(comparison: str, left: Path, right: Path) -> dict:
    ids = [ASSIGNMENT + "__park_narrow_device", ASSIGNMENT + "__" + comparison]
    attempts = [Path(left), Path(right)]
    for case_id, attempt in zip(ids, attempts):
        audit_diagnostic(case_id, attempt)
    cameras = [json.loads((attempt / "cameras.json").read_text()) for attempt in attempts]
    if cameras[0] != cameras[1] or cameras[0].get("frame_count") != 9:
        raise ValueError("fixed diagnostic camera protocol differs")
    packets = [{"case_id": case_id, "context": str(attempt / "context.json"),
                "trace": str(attempt / "original-trace.jsonl"),
                "receipt": str(attempt / "receipt.json")}
               for case_id, attempt in zip(ids, attempts)]
    result = audit_original(comparison, packets[0], packets[1], diagnostic=True)
    return dict(result, diagnostic_fixture=True,
                source_context_sha256=[sha(attempt / "context.json") for attempt in attempts],
                fixed_diagnostic_context_and_camera_protocol_checked=True,
                deliberate_difference_checked=True, original_fixed_sources_unverified=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.comparison, args.left, args.right),
                                      indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
