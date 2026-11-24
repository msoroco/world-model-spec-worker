"""Saved-only verification of the exact original Native sight source.

It remeasures the source rows and checks the acquisition seal. It does not
claim camera coverage, physical sight validity, or a legal speed judgment.
"""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from sight_measurement import evaluate


class SavedSightError(ValueError):
    pass


def verify(attempt: Path, expected_case: str) -> dict:
    source = attempt / "native-sight.json"
    receipt_path = attempt / "native-sight-receipt.json"
    if not source.is_file() or not receipt_path.is_file():
        raise SavedSightError("sealed original sight acquisition absent")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("source_path") != "native-sight.json":
        raise SavedSightError("source path differs from sealed acquisition")
    if receipt.get("source_sha256") != sha256(source.read_bytes()).hexdigest():
        raise SavedSightError("original sight source changed")
    packet = json.loads(source.read_text(encoding="utf-8"))
    if packet.get("case_id") != expected_case or receipt.get("case_id") != expected_case:
        raise SavedSightError("exact case identity differs")
    if receipt.get("recorded_only") is not True or receipt.get("capture_kind") != "original_native":
        raise SavedSightError("original Native capture required")
    if receipt.get("fps") != 20 or receipt.get("duration_s") != 45:
        raise SavedSightError("20 Hz, 45-second acquisition differs")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) != 900:
        raise SavedSightError("900 original sight frames required")
    if (frames[0].get("frame") != receipt.get("first_frame") or
            frames[-1].get("frame") != receipt.get("last_frame") or
            receipt.get("frame_count") != 900):
        raise SavedSightError("original frame receipt differs")
    def digest(value):
        raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        return sha256(raw).hexdigest()
    if digest(frames) != packet.get("frame_source_sha256"):
        raise SavedSightError("original frame seal differs")
    if digest([f["rays"] for f in frames]) != packet.get("ray_source_sha256"):
        raise SavedSightError("original ray seal differs")
    if digest([f["ego_speed_mps"] for f in frames]) != packet.get("speed_source_sha256"):
        raise SavedSightError("original speed seal differs")
    measured = evaluate(packet)
    if digest(measured) != digest(receipt.get("measurement")):
        raise SavedSightError("saved recomputation differs from Native receipt")
    return {"case_id": expected_case, "original_sight_join": "passed",
            "measurement": measured, "camera_capture": "unverified",
            "physical_visibility": "unverified", "legal_conclusion": None}
