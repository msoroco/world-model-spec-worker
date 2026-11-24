"""Full source decode and pixel check for a selected acquired original.

The decode receipt binds the exact sight frame map, media auditor version and
every decoded RGB frame. Pixel variation alone is not driver visibility.
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

from selected_media_audit import audit_acquired


def pixel_presence(frame):
    pixels = frame.pixels
    if len(pixels) != frame.width * frame.height * 3 or len(set(pixels)) < 3:
        raise ValueError("decoded frame lacks actual varied pixels")


def decode_selected(plan: dict, repository: Path, attempt: Path,
                    acquired: Path, receipt: Path) -> dict:
    repository = Path(repository).resolve()
    worker_root = Path(__file__).resolve().parents[2]
    output = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    scratch = worker_root / ".runtime-work"
    if not output.is_relative_to(scratch) or output == scratch:
        raise ValueError("pipeline output root must be under .runtime-work")
    selected = audit_acquired(plan, repository, attempt, acquired)
    receipt = Path(receipt)
    if receipt.exists():
        raise ValueError("refusing to overwrite source decode receipt")
    if not receipt.resolve().is_relative_to(scratch):
        raise ValueError("source decode receipt must be scratch")
    sys.path.insert(0, str(worker_root / "runtime" / "scenario_pipeline"))
    from worker_exchange.media import audit, verify_receipt
    checker = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    video = Path(acquired) / "raw.mkv"
    decoded = audit(video, 900, checkers={"pixel_presence": (checker, pixel_presence)},
                    mapping_sha256=selected["frame_map_sha256"], receipt=receipt)
    verify_receipt(video, receipt, 900, mapping_sha256=selected["frame_map_sha256"],
                   required_checks={"pixel_presence": checker})
    return {"case_id": selected["case_id"], "recording_id": selected["recording_id"],
            "video_sha256": selected["video_sha256"],
            "frame_map_sha256": selected["frame_map_sha256"],
            "decode_receipt_sha256": hashlib.sha256(receipt.read_bytes()).hexdigest(),
            "rgb_sequence_sha256": decoded["rgb_sequence_sha256"],
            "physical_visibility_judgment": "unresolved"}
