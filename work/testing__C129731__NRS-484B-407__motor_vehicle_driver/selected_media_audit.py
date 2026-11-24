"""Bind a selected reuse candidate to original metadata, trace and decoded media.

This source gate does not infer legal visibility or certify canonical acceptance.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from sight_measurement import measure


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
              if row.get("path", "").endswith(f"/accepted/{recording_id}/metadata.json")]
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
