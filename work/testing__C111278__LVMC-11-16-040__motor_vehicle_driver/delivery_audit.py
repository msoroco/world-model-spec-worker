"""Independent recorded-only audit before any case is considered delivered.

This verifies joins and provenance, not law, physical visibility, or video quality.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path


class DeliveryError(ValueError):
    pass


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def audit(receipt: dict, measurement: dict, source_root: Path, expected_case: str) -> dict:
    if receipt.get("case_id") != expected_case or measurement.get("case_id") != expected_case:
        raise DeliveryError("case binding differs")
    if receipt.get("map_hash") != measurement.get("map_hash"):
        raise DeliveryError("map identity differs")
    if receipt.get("recorded_only") is not True or receipt.get("capture_kind") != "original_native":
        raise DeliveryError("original saved acquisition required")
    if receipt.get("fps") != 20 or receipt.get("duration_s") != 45:
        raise DeliveryError("20 Hz, 45-second acquisition contract differs")
    streams = receipt.get("streams")
    if not isinstance(streams, dict) or set(streams) != set(CAMERAS):
        raise DeliveryError("four-camera source inventory incomplete")
    for name, item in streams.items():
        relative = item.get("path", "")
        if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise DeliveryError(f"unsafe or missing {name} path")
        file = source_root / relative
        if not file.is_file() or sha256(file.read_bytes()).hexdigest() != item.get("sha256"):
            raise DeliveryError(f"{name} bytes missing or changed")
    frame_ids = receipt.get("frame_ids")
    if not isinstance(frame_ids, list) or len(frame_ids) != 900:
        raise DeliveryError("full original frame map missing")
    if any(b != a + 1 for a, b in zip(frame_ids, frame_ids[1:])):
        raise DeliveryError("frame map not contiguous")
    if not set(measurement.get("approach_frame_ids", [])).issubset(frame_ids):
        raise DeliveryError("approach frames not in original acquisition")
    if not set(measurement.get("traversal_frame_ids", [])).issubset(frame_ids):
        raise DeliveryError("traversal frames not in original acquisition")
    if not measurement.get("source_sha256"):
        raise DeliveryError("measurement provenance absent")
    if receipt.get("candidate") not in ("primary", "fallback1", "fallback2"):
        raise DeliveryError("candidate-selection receipt absent")
    return {"case_id": expected_case, "recorded_only_join": "passed", "legal_conclusion": None}
