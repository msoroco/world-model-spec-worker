"""Verify original files for a frozen accepted C178244 recording.

This is a read-only admission check. An accepted metadata row alone is not a
signal-distance measurement, and this module makes no legal finding.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ASSIGNMENT = "testing__C178244__NRS-484B-413-2__motor_vehicle_driver"
PREFIX = ASSIGNMENT + "__"
SUFFIXES = {
    "business_continuous", "business_short", "residence_continuous",
    "residence_short", "other_area_continuous", "other_area_short",
}


class SourceError(ValueError):
    pass


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(repo: Path, recording_id: str, trace: Path, video: Path) -> dict:
    inventory = repo / "inputs" / ASSIGNMENT / "accepted" / recording_id / "metadata.json"
    if not inventory.is_file():
        raise SourceError("recording is absent from frozen accepted inventory")
    evidence_path = repo / "inputs" / ASSIGNMENT / "evidence.json"
    if not evidence_path.is_file():
        raise SourceError("frozen evidence inventory is missing")
    evidence = json.loads(evidence_path.read_text())
    members = [row for row in evidence.get("recordings", [])
               if row.get("recording_id") == recording_id]
    if len(members) != 1 or {"path": str(inventory.relative_to(repo)),
                             "sha256": sha(inventory)} not in members[0].get("sources", []):
        raise SourceError("accepted metadata differs from frozen evidence inventory")
    metadata = json.loads(inventory.read_text())
    case_id = metadata.get("case_id")
    if (metadata.get("recording_id") != recording_id or
            metadata.get("cell_id") != "C178244" or
            metadata.get("actor") != "motor_vehicle_driver" or
            metadata.get("law_id") != "NRS-484B-413-2" or
            not isinstance(case_id, str) or not case_id.startswith(PREFIX) or
            case_id[len(PREFIX):] not in SUFFIXES or
            metadata.get("status") != "accepted"):
        raise SourceError("frozen accepted recording identity mismatch")
    membership = members[0].get("membership") or {}
    if any(membership.get(key) != metadata.get(key) for key in
           ("recording_id", "case_id", "cell_id", "actor", "law_id", "status")):
        raise SourceError("accepted membership differs from metadata")
    if not trace.is_file() or not video.is_file():
        raise SourceError("original trace or video file is missing")
    trace_hash, video_hash = sha(trace), sha(video)
    if trace_hash != metadata.get("trace_sha256"):
        raise SourceError("original trace hash differs from accepted inventory")
    if video_hash != metadata.get("video_sha256"):
        raise SourceError("original video hash differs from accepted inventory")
    acceptance = metadata.get("acceptance") or {}
    if (acceptance.get("trace_sha256") != trace_hash or
            acceptance.get("video_sha256") != video_hash or
            acceptance.get("case_id") != case_id or
            acceptance.get("frames") != metadata.get("frames")):
        raise SourceError("acceptance source binding differs from metadata")
    return {
        "format": "accepted-original-source-admission",
        "assignment_id": ASSIGNMENT,
        "recording_id": recording_id,
        "case_id": case_id,
        "metadata_sha256": sha(inventory),
        "trace_sha256": trace_hash,
        "video_sha256": video_hash,
        "frames_declared": metadata["frames"],
        "finding": "original bytes admitted by frozen hashes; signal readback, district, turn onset, full decode and comparison still require independent audit",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--recording-id", required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.repo.resolve(), args.recording_id,
                            args.trace, args.video), sort_keys=True))


if __name__ == "__main__":
    main()
