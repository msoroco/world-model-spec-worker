"""Bind a selected reuse candidate to original metadata, trace and decoded media.

This source gate does not infer legal visibility or certify canonical acceptance.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from sight_measurement import measure
from comparison_audit import audit as audit_comparison


def _digest(path: Path) -> str:
    if not path.is_file():
        raise ValueError("selected original source missing")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_selected(plan: dict, repository: Path, attempt: Path,
                   video: Path, trace: Path) -> dict:
    attempt = Path(attempt)
    inventory = json.loads((attempt / "inventory.json").read_text())
    case_id, recording_id = inventory.get("case_id"), inventory.get("recording_id")
    matches = [row for row in plan.get("accepted_reuse_candidates", [])
               if row.get("case_id") == case_id and row.get("recording_id") == recording_id]
    if len(matches) != 1:
        raise ValueError("selected case/recording identity absent from plan")
    source = [row for row in plan.get("sources", [])
              if Path(row.get("path", "")).parts[-3:] ==
              ("accepted", recording_id, "metadata.json")]
    if len(source) != 1:
        raise ValueError("selected frozen metadata source absent")
    rel = Path(source[0]["path"])
    repository = Path(repository).resolve()
    meta_path = (repository / rel).resolve()
    if rel.is_absolute() or not meta_path.is_relative_to(repository):
        raise ValueError("selected metadata path escapes repository")
    if _digest(meta_path) != source[0]["sha256"]:
        raise ValueError("selected metadata source hash mismatch")
    metadata = json.loads(meta_path.read_text())
    if (metadata.get("recording_id") != recording_id or metadata.get("case_id") != case_id or
            metadata.get("status") != "accepted" or metadata.get("frames") != 900):
        raise ValueError("selected frozen metadata identity or frame count mismatch")
    video_sha, trace_sha = _digest(Path(video)), _digest(Path(trace))
    if video_sha != metadata.get("video_sha256") or trace_sha != metadata.get("trace_sha256"):
        raise ValueError("selected media or trace hash mismatch")
    decoded = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=codec_type,nb_read_frames,r_frame_rate,width,height",
         "-of", "json", str(video)], capture_output=True, text=True, check=False)
    if decoded.returncode:
        raise ValueError("selected video full decode failed")
    streams = json.loads(decoded.stdout).get("streams", [])
    if len(streams) != 1 or streams[0].get("nb_read_frames") != "900" or \
            streams[0].get("r_frame_rate") != "20/1" or \
            not streams[0].get("width") or not streams[0].get("height"):
        raise ValueError("selected video 900-frame 20 Hz contract failed")
    measured = measure(attempt, inventory, case_id)
    return {"format": "c129731-selected-reuse-media-v1", "case_id": case_id,
            "recording_id": recording_id, "metadata_sha256": source[0]["sha256"],
            "video_sha256": video_sha, "trace_sha256": trace_sha,
            "frame_map_sha256": measured["source_sha256"]["frame_map"],
            "decoded_video_frames": 900, "sight_measurement": measured,
            "legal_visibility_judgment": "unresolved",
            "canonical_acceptance": "unresolved"}


def audit_selected_pair(plan: dict, repository: Path, comparison_id: str,
                        left: tuple[Path, Path, Path],
                        right: tuple[Path, Path, Path]) -> dict:
    """Require independently bound media and measured sight difference on both sides."""
    left_result = audit_selected(plan, repository, *left)
    right_result = audit_selected(plan, repository, *right)
    if (left_result["video_sha256"] == right_result["video_sha256"] or
            left_result["trace_sha256"] == right_result["trace_sha256"]):
        raise ValueError("comparison reused video or trace bytes")
    left_inventory = json.loads((Path(left[0]) / "inventory.json").read_text())
    right_inventory = json.loads((Path(right[0]) / "inventory.json").read_text())
    comparison = audit_comparison(plan, comparison_id, left[0], left_inventory,
                                  right[0], right_inventory)
    return {"format": "c129731-selected-reuse-pair-v1",
            "comparison": comparison, "selected_media": [left_result, right_result],
            "canonical_acceptance": "unresolved"}


def audit_acquired(plan: dict, repository: Path, attempt: Path,
                   acquired: Path) -> dict:
    """Reread the acquisition receipt and copied bytes before media/sight audit."""
    acquired = Path(acquired)
    receipt = json.loads((acquired / "acquisition.json").read_text())
    if receipt.get("format") != "c129731-original-source-acquisition-v1":
        raise ValueError("original acquisition receipt format mismatch")
    inventory = json.loads((Path(attempt) / "inventory.json").read_text())
    if (receipt.get("case_id") != inventory.get("case_id") or
            receipt.get("recording_id") != inventory.get("recording_id")):
        raise ValueError("original acquisition identity mismatch")
    for kind, name in (("video", "raw.mkv"), ("trace", "trace.json")):
        entry = receipt.get("sources", {}).get(kind, {})
        if entry.get("path") != name or _digest(acquired / name) != entry.get("sha256"):
            raise ValueError("acquired original source hash mismatch")
    result = audit_selected(plan, repository, attempt,
                            acquired / "raw.mkv", acquired / "trace.json")
    if receipt.get("metadata_sha256") != result["metadata_sha256"]:
        raise ValueError("acquired original metadata hash mismatch")
    return result
