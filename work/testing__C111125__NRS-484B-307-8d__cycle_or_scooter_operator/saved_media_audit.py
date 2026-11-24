"""Independently decode and join every saved original bicycle camera image."""
from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from PIL import Image


ASSIGNMENT_ID = "testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
PROFILE_SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
                 "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def _verified_path(root: Path, ref: dict) -> Path:
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not isinstance(ref.get("sha256"), str):
        raise ValueError("original source reference missing")
    path = (root / ref["path"]).resolve()
    if path.parent != root or not path.is_file():
        raise ValueError("original source file missing or outside attempt")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != ref["sha256"]:
        raise ValueError("original source hash mismatch")
    return path


def audit_saved_media(attempt_root: Path, case_id: str) -> dict:
    root = Path(attempt_root).resolve()
    receipt_path = root / "attempt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("format") != "c111125-native-attempt-v1" or receipt.get("case_id") != case_id or not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("original attempt identity differs")
    if receipt.get("native_exit_code") != 0 or receipt.get("camera_capture_complete") is not True:
        raise ValueError("original Native or four-camera capture incomplete")
    packet = json.loads(_verified_path(root, receipt.get("packet_ref")).read_text(encoding="utf-8"))
    rows = packet.get("frames")
    if not isinstance(rows, list) or len(rows) != receipt.get("frame_count") or len(rows) < 2:
        raise ValueError("original frame count differs")
    first = rows[0].get("frame")
    first_time = rows[0].get("timestamp_s")
    if not isinstance(first, int) or not isinstance(first_time, (int, float)):
        raise ValueError("original frame identity missing")
    for index, row in enumerate(rows):
        if row.get("frame") != first + index or not isinstance(row.get("timestamp_s"), (int, float)) or abs(row["timestamp_s"] - first_time - index / 20) > 0.001:
            raise ValueError("original 20 Hz frame/time join differs")
    sources = receipt.get("camera_sources")
    if not isinstance(sources, dict) or set(sources) != set(CAMERAS):
        raise ValueError("four original camera sources missing")
    dimensions = {}
    for name in CAMERAS:
        source = sources[name]
        if source.get("frame_count") != len(rows):
            raise ValueError("original camera frame count differs: " + name)
        path = _verified_path(root, source)
        with ZipFile(path) as archive:
            members = [f"{row['frame']:08d}.png" for row in rows]
            if archive.namelist() != members:
                raise ValueError("original camera frame map differs: " + name)
            for row, member in zip(rows, members):
                payload = archive.read(member)
                binding = row.get("camera_frames", {}).get(name)
                if binding != {"member": member, "sha256": hashlib.sha256(payload).hexdigest()}:
                    raise ValueError("original camera pixel binding differs: " + name)
                with Image.open(BytesIO(payload)) as image:
                    image.verify()
                with Image.open(BytesIO(payload)) as image:
                    if image.format != "PNG":
                        raise ValueError("original camera image is not PNG: " + name)
                    image.load()
                    size = tuple(image.size)
                if name in dimensions and dimensions[name] != size:
                    raise ValueError("original camera dimensions vary: " + name)
                if receipt.get("diagnostic_fixture") is not True and size != PROFILE_SIZES[name]:
                    raise ValueError("original camera profile differs: " + name)
                dimensions[name] = size
    return {"format": "c111125-original-media-audit-v1", "assignment_id": ASSIGNMENT_ID,
            "case_id": case_id, "attempt_receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
            "frame_count": len(rows), "decoded_original_images": len(rows) * len(CAMERAS),
            "camera_dimensions": {key: list(value) for key, value in dimensions.items()},
            "diagnostic_fixture": receipt.get("diagnostic_fixture") is True,
            "physical_acceptance": False, "legal_verdict": None}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_saved_media(args.attempt, args.case_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
