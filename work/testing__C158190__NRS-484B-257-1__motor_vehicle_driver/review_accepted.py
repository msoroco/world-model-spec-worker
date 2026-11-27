"""Inspect the Core trace structure after admitting original frozen source bytes.

The Core trace contains scenes and timestamps. It does not itself supply the
site survey or measured stop/crosswalk observations needed for a physical or
legal finding about this assignment.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from accepted_source import SourceError, verify


def review(repo: Path, recording_id: str, trace: Path, video: Path) -> dict:
    admission = verify(repo, recording_id, trace, video)
    try:
        original = json.loads(trace.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceError("original Core trace is unreadable") from exc
    if not isinstance(original, dict) or not isinstance(original.get("scenes"), list):
        raise SourceError("original Core trace scenes are missing")
    scenes = original["scenes"]
    if len(scenes) != admission["frames_declared"]:
        raise SourceError("complete original Core scene history is missing")
    timestamps = []
    for scene in scenes:
        if not isinstance(scene, dict) or isinstance(scene.get("t"), bool) or not isinstance(scene.get("t"), int):
            raise SourceError("original Core scene timestamp is missing")
        timestamp = scene["t"]
        if timestamps and timestamp <= timestamps[-1]:
            raise SourceError("original Core scene timestamps must increase")
        timestamps.append(timestamp)
    return {
        "format": "accepted-core-trace-structure-review",
        "assignment_id": admission["assignment_id"],
        "recording_id": recording_id,
        "case_id": admission["case_id"],
        "admission": admission,
        "original_observations": {
            "scene_count": len(scenes),
            "first_timestamp_ms": timestamps[0],
            "last_timestamp_ms": timestamps[-1],
        },
        "finding": "Source-bound Core trace structure only; stop-sign governance, crosswalk geometry, stopping location, traffic response, video pixels, and legal coverage require separately bound original evidence and review.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--recording-id", required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(review(args.repo.resolve(), args.recording_id,
                            args.trace, args.video), sort_keys=True))


if __name__ == "__main__":
    main()
