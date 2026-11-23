"""Saved-only parked-lamp finalizer from sealed original Native source files.

This worker finalizer produces measurements and explicit unknowns. The pinned
converter, Lean decoder, renderer and video decoder still need compatibility
proof before delivery readiness.
"""

import argparse
import json
from pathlib import Path

from parked_lamps import audit_saved_capture, digest, measure, require


def finalize(capture_dir, case_key, site_path, expected_map_sha256):
    capture_dir = Path(capture_dir)
    site_path = Path(site_path)
    require(site_path.is_file(), "site source absent")
    site = json.loads(site_path.read_text())
    packet = json.loads((capture_dir / "capture-packet.json").read_text())
    require(packet.get("site_packet_sha256") == digest(site_path), "site packet seal mismatch")
    require(packet.get("site_source_sha256") == site.get("site_source_sha256"), "site evidence source seal mismatch")
    sealed = audit_saved_capture(capture_dir, case_key, expected_map_sha256)
    rows_path = capture_dir / packet.get("original_history_path", "")
    require(rows_path.is_file() and rows_path.resolve().is_relative_to(capture_dir.resolve()), "original history absent")
    require(packet.get("original_history_sha256") == digest(rows_path), "original history seal mismatch")
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    measured = measure(site, case_key, expected_map_sha256, rows)
    return {"format": "c229398-source-bound-original-measurement-v1", "saved_capture": sealed,
            "site_packet_sha256": digest(site_path), "original_history_sha256": digest(rows_path),
            "measurement": measured, "physical_visibility_status": "requires_original_video_review",
            "legal_verdict": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", required=True)
    parser.add_argument("--case-key", required=True)
    parser.add_argument("--site", required=True)
    parser.add_argument("--map-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = finalize(args.capture, args.case_key, args.site, args.map_sha256)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
