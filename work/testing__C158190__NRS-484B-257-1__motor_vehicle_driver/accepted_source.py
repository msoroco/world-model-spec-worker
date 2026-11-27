"""Admit original bytes for the two frozen accepted C158190 records.

Metadata is an inventory, not evidence that a stop or crosswalk was observed.
This check reads no mutable worker claim about physical or legal coverage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ASSIGNMENT = "testing__C158190__NRS-484B-257-1__motor_vehicle_driver"
CASES = {
    "e500db67c018ddd9928da09eb7e3d0e039881e3f2c65e9e34b8566df1d8626ee":
        ASSIGNMENT + "__near_side_sidewalk_derived_crosswalk_response",
    "9f9884de772c537608d1a3c2d71c4be6e2526081cc3689466a6ae72faf39b7c6":
        ASSIGNMENT + "__near_side_sidewalk_derived_crosswalk_uninterrupted",
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
    if recording_id not in CASES:
        raise SourceError("recording is not one of the two frozen accepted IDs")
    source = repo / "inputs" / ASSIGNMENT
    inventory = source / "accepted" / recording_id / "metadata.json"
    evidence_path = source / "evidence.json"
    assignment_path = source / "assignment.json"
    if not all(path.is_file() for path in (inventory, evidence_path, assignment_path)):
        raise SourceError("frozen assignment, evidence, or metadata is missing")
    assignment = json.loads(assignment_path.read_text())
    if (assignment.get("assignment_id") != ASSIGNMENT or
            assignment.get("cell", {}).get("cell_id") != "C158190" or
            assignment.get("cell", {}).get("control") != "stop_sign"):
        raise SourceError("frozen C158190 stop-sign assignment identity differs")
    evidence = json.loads(evidence_path.read_text())
    rows = [row for row in evidence.get("recordings", [])
            if row.get("recording_id") == recording_id]
    expected_source = {"path": str(inventory.relative_to(repo)), "sha256": sha(inventory)}
    if len(rows) != 1 or expected_source not in rows[0].get("sources", []):
        raise SourceError("metadata differs from frozen evidence inventory")
    row = json.loads(inventory.read_text())
    identity = {"recording_id": recording_id, "case_id": CASES[recording_id],
                "cell_id": "C158190", "actor": "motor_vehicle_driver",
                "law_id": "NRS-484B-257-1", "status": "accepted"}
    if any(row.get(key) != value for key, value in identity.items()):
        raise SourceError("frozen accepted recording identity differs")
    membership = rows[0].get("membership") or {}
    if any(membership.get(key) != value for key, value in identity.items()):
        raise SourceError("frozen accepted membership identity differs")
    if set(rows[0].get("sets", [])) != {"demo-test", "full-test"}:
        raise SourceError("frozen accepted set membership differs")
    acceptance = row.get("acceptance") or {}
    trace_source = acceptance.get("trace_source")
    video_source = acceptance.get("video_source")
    suffix = "/recordings/" + recording_id + "/evidence/"
    if (not isinstance(trace_source, str) or not isinstance(video_source, str) or
            not trace_source.endswith(suffix + "traffic_spec/trace.json") or
            video_source != trace_source[:-(len("traffic_spec/trace.json"))] + "raw.mkv"):
        raise SourceError("frozen original source paths differ")
    if any(acceptance.get(key) != value for key, value in
           {**identity, "split": "testing"}.items() if key in acceptance):
        raise SourceError("accepted source identity differs")
    if (acceptance.get("case_id") != identity["case_id"] or
            acceptance.get("cell_id") != "C158190" or
            acceptance.get("actor") != "motor_vehicle_driver" or
            acceptance.get("law_id") != "NRS-484B-257-1" or
            acceptance.get("split") != "testing" or
            row.get("frames") != 900 or acceptance.get("frames") != 900):
        raise SourceError("accepted source frame or case binding differs")
    if not trace.is_file() or not video.is_file() or trace.is_symlink() or video.is_symlink():
        raise SourceError("original trace or video bytes are missing")
    trace_hash, video_hash = sha(trace), sha(video)
    if trace_hash != row.get("trace_sha256") or trace_hash != acceptance.get("trace_sha256"):
        raise SourceError("original trace hash differs from frozen acceptance")
    if video_hash != row.get("video_sha256") or video_hash != acceptance.get("video_sha256"):
        raise SourceError("original video hash differs from frozen acceptance")
    return {
        "format": "accepted-original-source-admission",
        "assignment_id": ASSIGNMENT,
        "recording_id": recording_id,
        "case_id": identity["case_id"],
        "metadata_sha256": sha(inventory),
        "trace_sha256": trace_hash,
        "video_sha256": video_hash,
        "frames_declared": 900,
        "finding": "Original bytes match frozen hashes; stop governance, crosswalk geometry, motion, video decode, and legal coverage remain unverified.",
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
