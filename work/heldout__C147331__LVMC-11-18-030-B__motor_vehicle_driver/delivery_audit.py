"""Independent saved source and complete camera audit for C147331 cases.

This checks software evidence only. Physical visibility, municipal applicability,
lawful passing and actual completion remain for independent local review.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from lane_finalizer import analyze


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("video_frames.jsonl", "trace.jsonl", "marked_lane_sources.jsonl")


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def audit_attempt(attempt, report, *, decoder=None, receipt_dir=None):
    root = Path(attempt)
    report = json.loads(Path(report).read_text()) if not isinstance(report, dict) else report
    for name in (*SOURCES, "config.json"):
        if not (root / name).is_file():
            raise ValueError("Missing audited original lane source: " + name)
    sources = report["measurements"]["lane_boundary_observation"]["sources"]
    if set(sources) != set(SOURCES):
        raise ValueError("Lane analysis source inventory differs")
    if any(digest(root / name) != expected for name, expected in sources.items()):
        raise ValueError("Lane analysis source hash differs")
    independent = analyze(root, write_channel=False)
    if independent["case_id"] != report["case_id"] or independent["measurements"] != report["measurements"]:
        raise ValueError("Lane analysis differs from recomputed original sources")
    mapping = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
    if not mapping:
        raise ValueError("No original lane frames")
    if decoder is None:
        from worker_exchange.media import audit as decoder
    if receipt_dir is not None:
        Path(receipt_dir).mkdir(parents=True, exist_ok=False)
    camera_receipts = {}
    for name in CAMERAS:
        source = root / (name + ".mkv")
        if not source.is_file():
            raise ValueError("Missing named lane source camera: " + name)
        receipt = None if receipt_dir is None else Path(receipt_dir) / (name + "-decode.json")
        decoded = decoder(source, len(mapping),
                          mapping_sha256=digest(root / "video_frames.jsonl"), receipt=receipt)
        if decoded.get("frames") != len(mapping):
            raise ValueError("Named lane camera frame count differs: " + name)
        camera_receipts[name] = {"source_sha256": digest(source), "decode": decoded}
    return {"format": "worker-lane-source-audit", "case_id": report["case_id"],
            "source_hashes": sources, "frame_count": len(mapping),
            "camera_decodes": camera_receipts,
            "measurement_recomputed": True, "physical_visibility_claimed": False,
            "legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("Retain previous lane audit")
    receipt = audit_attempt(args.attempt, args.analysis,
                            receipt_dir=output.parent / (output.stem + "-decodes"))
    output.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
