"""Independent saved-source integrity gate for exact left-turn approach attempts.

This does not decode media or decide whether the statutory position was nearest.
The pinned compatibility and physical delivery audits remain separate proofs.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from approach import measure


PREFIX = "testing__C109705__NRS-484B-400-2a__motor_vehicle_driver__"
SUFFIXES = {
    "near_centerline", "farther_from_centerline",
    "imaginary_near_centerline", "imaginary_farther_from_centerline",
}
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}
FRAMES = 900


def _inside(attempt: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("invalid original media path")
    path = (attempt / relative).resolve()
    if not path.is_relative_to(attempt.resolve()) or not path.is_file():
        raise ValueError("original media missing or outside attempt")
    return path


def audit(attempt: Path, case_id: str, *, allow_diagnostic: bool = False) -> dict:
    """Reopen the exact original trace, frame map, context and four media files."""
    if case_id not in {PREFIX + suffix for suffix in SUFFIXES}:
        raise ValueError("unknown exact approach case")
    attempt = Path(attempt)
    acquisition = json.loads((attempt / "acquisition.json").read_text())
    if acquisition.get("case_id") != case_id:
        raise ValueError("original acquisition case differs")
    if acquisition.get("diagnostic_fixture") is not False and not allow_diagnostic:
        raise ValueError("diagnostic or unproven original source rejected")
    measured = measure(attempt)
    context = json.loads((attempt / "intersection-context.json").read_text())
    expected_kind = "imaginary_equidistant" if "__imaginary_" in case_id else "marked"
    if context["centerline_kind"] != expected_kind:
        raise ValueError("case and original centerline kind differ")
    rows = [json.loads(line) for line in (attempt / "approach-history.jsonl").read_text().splitlines()
            if line.strip()]
    frames = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines()
              if line.strip()]
    if len(rows) != FRAMES or len(frames) != FRAMES:
        raise ValueError("original 900-frame duration missing")
    origin = rows[0]["frame"]
    first_time = rows[0]["time_s"]
    if type(origin) is not int or type(first_time) not in (int, float) or not math.isfinite(first_time):
        raise ValueError("invalid original frame origin")
    for index, (row, frame) in enumerate(zip(rows, frames)):
        if (row["frame"] != origin + index or frame["frame"] != origin + index or
                abs(row["time_s"] - first_time - index / 20) > 1e-4 or
                abs(frame["time_s"] - row["time_s"]) > 1e-4):
            raise ValueError("original 20 Hz duration or camera join differs")
    media = acquisition.get("media")
    if not isinstance(media, dict) or set(media) != CAMERAS:
        raise ValueError("four original media sources missing")
    media_hashes = {}
    for camera in sorted(CAMERAS):
        declared = media[camera]
        if not isinstance(declared, dict) or declared.get("kind") != "original_native":
            raise ValueError(camera + " original media binding invalid")
        path = _inside(attempt, declared.get("path"))
        if path.stat().st_size == 0:
            raise ValueError(camera + " original media empty")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != declared.get("sha256"):
            raise ValueError(camera + " original media hash differs")
        media_hashes[camera] = actual
    return {
        "format": "worker-400-2a-saved-integrity-v1",
        "case_id": case_id,
        "frame_count": FRAMES,
        "source_sha256": measured["source_sha256"],
        "media_sha256": media_hashes,
        "approach_body_measurement": measured,
        "source_integrity_passed": True,
        "full_video_decode": False,
        "actual_pixels": False,
        "physical_completion": False,
        "legal_judgment": "unresolved",
    }
