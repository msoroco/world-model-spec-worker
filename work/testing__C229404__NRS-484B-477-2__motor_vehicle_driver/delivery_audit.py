"""Independent saved-source audit for an alley-access attempt.

This validates sealed source joins and camera archives. Full pixel decoding and
physical/legal review remain separate local acceptance steps.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from access_measurement import measure
from native_capture import CAMERAS, FRAMES


def audit(attempt: Path, case_id: str, *, require_original: bool = True) -> dict:
    root = Path(attempt)
    inventory = json.loads((root / "inventory.json").read_text())
    if require_original and inventory.get("diagnostic_fixture") is not False:
        raise ValueError("diagnostic fixture cannot satisfy original delivery")
    measurement = measure(root, inventory, case_id)
    raw_map = (root / "road.xodr").read_bytes()
    if hashlib.sha256(raw_map).hexdigest() != inventory.get("map_sha256"):
        raise ValueError("saved Native map hash changed")
    media = inventory.get("media")
    if not isinstance(media, dict) or set(media) != CAMERAS:
        raise ValueError("complete four-camera source inventory missing")
    frame_map = json.loads((root / inventory["sources"]["frame_map"]["path"]).read_text())["frames"]
    if len(frame_map) != FRAMES:
        raise ValueError("camera frame map incomplete")
    for name in sorted(CAMERAS):
        item = media[name]
        path = root / item["path"]
        if path.name != name + ".zip" or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("original camera archive changed: " + name)
        with zipfile.ZipFile(path) as archive:
            expected = [f"{i:04d}-{row['frame']}.png" for i, row in enumerate(frame_map)]
            if archive.namelist() != expected:
                raise ValueError("original camera frame join changed: " + name)
            if any(not archive.read(member).startswith(b"\x89PNG\r\n\x1a\n") for member in expected):
                raise ValueError("original camera PNG missing: " + name)
    return {"format": "c229404-saved-source-audit-v1", "case_id": case_id,
            "frame_count": FRAMES, "media_sha256": {name: media[name]["sha256"] for name in sorted(CAMERAS)},
            "measurement_source_sha256": measurement["source_sha256"],
            "max_access_intrusion_area_m2": measurement["max_access_intrusion_area_m2"],
            "statutory_blocking_judgment": "unresolved",
            "physical_completion": False}
