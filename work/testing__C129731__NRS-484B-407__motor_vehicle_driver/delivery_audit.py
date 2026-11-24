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

from selected_media_audit import audit_acquired


CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review(plan: dict, repository: Path, attempt: Path, acquired: Path,
           decode_receipt: Path) -> dict:
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
