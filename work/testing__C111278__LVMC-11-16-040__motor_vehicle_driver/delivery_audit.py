"""Independent recorded-only audit before any case is considered delivered.

This verifies joins and provenance, not law, physical visibility, or video quality.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import subprocess


class DeliveryError(ValueError):
    pass


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _decode_video(path: Path, expected_frames: int) -> dict:
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i",
               str(path), "-an", "-f", "framemd5", "-"]
    process = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if process.returncode:
        raise DeliveryError("full video decode failed: " + path.name)
    rows = [line for line in process.stdout.splitlines() if line and not line.startswith("#")]
    if len(rows) != expected_frames:
        raise DeliveryError("full video frame count differs: " + path.name)
    return {"decoded_frames": len(rows), "decoded_pixel_records_sha256": sha256(process.stdout.encode()).hexdigest()}


def audit(receipt: dict, measurement: dict, source_root: Path, expected_case: str,
          full_video_decode: bool = False) -> dict:
    if receipt.get("case_id") != expected_case or measurement.get("case_id") != expected_case:
        raise DeliveryError("case binding differs")
    if receipt.get("map_hash") != measurement.get("map_hash"):
        raise DeliveryError("map identity differs")
    diagnostic = receipt.get("diagnostic_fixture") is True
    if diagnostic:
        source = source_root / "fixture-provenance.json"
        if (receipt.get("capture_kind") != "synthetic_fixture" or not source.is_file() or
                json.loads(source.read_text()).get("physical_acceptance_claimed") is not False):
            raise DeliveryError("untrusted synthetic audit source")
    elif receipt.get("recorded_only") is not True or receipt.get("capture_kind") != "original_native":
        raise DeliveryError("original saved acquisition required")
    if receipt.get("fps") != 20 or receipt.get("duration_s") != 45:
        raise DeliveryError("20 Hz, 45-second acquisition contract differs")
    streams = receipt.get("streams")
    if not isinstance(streams, dict) or set(streams) != set(CAMERAS):
        raise DeliveryError("four-camera source inventory incomplete")
    decoded = {}
    for name, item in streams.items():
        relative = item.get("path", "")
        if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise DeliveryError(f"unsafe or missing {name} path")
        file = source_root / relative
        if not file.is_file() or sha256(file.read_bytes()).hexdigest() != item.get("sha256"):
            raise DeliveryError(f"{name} bytes missing or changed")
        if full_video_decode:
            decoded[name] = _decode_video(file, 900)
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
    if full_video_decode:
        census_path = source_root / "actor-census.jsonl"
        if (not census_path.is_file() or
                sha256(census_path.read_bytes()).hexdigest() != receipt.get("actor_census_sha256")):
            raise DeliveryError("actor census missing or changed")
        census = [json.loads(line) for line in census_path.read_text().splitlines()]
        arms = receipt.get("entering_arms")
        if (not isinstance(arms, list) or len(arms) < 3 or
                len(census) != 900 or
                any(row.get("frame") != frame or row.get("entering_arms") != arms or
                    not isinstance(row.get("actors"), list)
                    for row, frame in zip(census, frame_ids))):
            raise DeliveryError("all-frame entering-arm actor inventory incomplete")
    if receipt.get("candidate") not in ("primary", "fallback1", "fallback2"):
        raise DeliveryError("candidate-selection receipt absent")
    return {"case_id": expected_case, "recorded_only_join": "passed",
            "full_video_decode": decoded, "diagnostic_fixture": diagnostic,
            "legal_conclusion": None}
