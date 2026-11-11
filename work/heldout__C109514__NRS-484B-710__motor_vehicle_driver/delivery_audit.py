"""Independent original-source audit for the fire-apparatus exact case.

This audits saved acquisition bytes and complete source-camera decoding.  It
cannot establish physical visibility or legal acceptance from a CPU fixture.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
REQUIRED = ("video_frames.jsonl", "trace.jsonl", "participant_footprints.jsonl",
            "participant_state.jsonl", "fire_context.json")


def _hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _finalizer():
    source = Path(__file__).with_name("fire_finalizer.py")
    spec = importlib.util.spec_from_file_location("fire_finalizer_audited", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit_attempt(attempt, report, *, decoder=None, receipt_dir=None):
    root = Path(attempt)
    report = json.loads(Path(report).read_text()) if not isinstance(report, dict) else report
    for name in (*REQUIRED, "config.json"):
        if not (root / name).is_file():
            raise ValueError("Missing audited original source: " + name)
    source_hashes = report["measurements"]["fire_boundary_observation"]["sources"]
    if set(source_hashes) != set(REQUIRED):
        raise ValueError("Analysis source inventory is incomplete or unexpected")
    if any(_hash(root / name) != expected for name, expected in source_hashes.items()):
        raise ValueError("Analysis source hash differs from retained acquisition")
    independent = _finalizer().analyze(root, write_channel=False)
    if independent["case_id"] != report["case_id"]:
        raise ValueError("Analysis case identity differs")
    if independent["measurements"] != report["measurements"]:
        raise ValueError("Analysis measurements differ from recomputed originals")
    frame_map = _rows(root / "video_frames.jsonl")
    trace = _rows(root / "trace.jsonl")
    if not frame_map or len(frame_map) != len(trace):
        raise ValueError("Original source frame count differs")
    for i, (mapping, row) in enumerate(zip(frame_map, trace)):
        if (mapping["video_frame"] != i or mapping["carla_frame"] != row["frame"]
                or mapping["time_s"] != row["time_s"]):
            raise ValueError("Original source frame identity differs")
    if decoder is None:
        from worker_exchange.media import audit as decoder
    if receipt_dir is not None:
        Path(receipt_dir).mkdir(parents=True, exist_ok=False)
    receipts = {}
    for camera in CAMERAS:
        path = root / (camera + ".mkv")
        if not path.is_file():
            raise ValueError("Missing named original camera: " + camera)
        receipt = None if receipt_dir is None else Path(receipt_dir) / (camera + "-decode.json")
        observed = decoder(path, len(frame_map),
                           mapping_sha256=_hash(root / "video_frames.jsonl"),
                           receipt=receipt)
        if observed.get("frames") != len(frame_map):
            raise ValueError("Named camera full decode frame count differs: " + camera)
        receipts[camera] = {"source_sha256": _hash(path), "decode": observed}
    return {"format": "worker-fire-source-audit", "case_id": report["case_id"],
            "original_source_hashes": source_hashes,
            "frame_count": len(frame_map), "camera_decodes": receipts,
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
        raise ValueError("Retain previous audit receipt; choose a fresh output")
    receipt = audit_attempt(args.attempt, args.analysis,
                            receipt_dir=output.parent / (output.stem + "-decodes"))
    output.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
